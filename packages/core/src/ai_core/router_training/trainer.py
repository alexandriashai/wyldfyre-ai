"""
MFRouter training wrapper for ContentRouter.

Provides a simplified interface for training the matrix factorization
router model used for content-based model tier selection.
"""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import torch
import yaml

from ..logging import get_logger

logger = get_logger(__name__)


@dataclass
class TrainingConfig:
    """Configuration for MFRouter training."""

    # Model hyperparameters
    latent_dim: int = 128
    text_dim: int = 768
    learning_rate: float = 0.001
    epochs: int = 50
    batch_size: int = 32

    # Paths (relative to config directory)
    config_dir: str = "/home/wyld-core/config/router"
    training_data_file: str = "training_data.jsonl"
    embeddings_dir: str = "embeddings"
    model_dir: str = "model"
    model_file: str = "mfrouter.pt"

    # Cost configuration for analytics
    cost_per_1k_tokens: dict[str, dict[str, float]] = field(
        default_factory=lambda: {
            "fast": {"input": 0.00025, "output": 0.00125},
            "balanced": {"input": 0.003, "output": 0.015},
            "powerful": {"input": 0.015, "output": 0.075},
        }
    )

    @property
    def training_data_path(self) -> Path:
        return Path(self.config_dir) / self.training_data_file

    @property
    def embeddings_path(self) -> Path:
        return Path(self.config_dir) / self.embeddings_dir / "query_embeddings.pt"

    @property
    def model_path(self) -> Path:
        return Path(self.config_dir) / self.model_dir / self.model_file

    @property
    def yaml_path(self) -> Path:
        return Path(self.config_dir) / "router_config.yaml"

    def to_yaml_config(self) -> dict:
        """Convert to YAML config format expected by MFRouter."""
        return {
            "hparam": {
                "latent_dim": self.latent_dim,
                "text_dim": self.text_dim,
                "lr": self.learning_rate,
                "epochs": self.epochs,
                "batch_size": self.batch_size,
            },
            "model_path": {
                "save_model_path": f"{self.model_dir}/{self.model_file}",
                "load_model_path": f"{self.model_dir}/{self.model_file}",
            },
            "data_path": {
                "routing_data_train": self.training_data_file,
                "query_embedding_data": f"{self.embeddings_dir}/query_embeddings.pt",
            },
            "cost_per_1k_tokens": self.cost_per_1k_tokens,
        }


class RouterTrainer:
    """
    Wrapper for training MFRouter models.

    Handles embedding generation, model training, and evaluation.
    """

    def __init__(self, config: TrainingConfig | None = None):
        self.config = config or TrainingConfig()
        self._embedding_model = None
        self._tokenizer = None

    def _ensure_directories(self):
        """Create necessary directories."""
        self.config.embeddings_path.parent.mkdir(parents=True, exist_ok=True)
        self.config.model_path.parent.mkdir(parents=True, exist_ok=True)

    def _get_embedding_model(self):
        """Lazy-load the embedding model (Longformer)."""
        if self._embedding_model is None:
            try:
                from transformers import AutoModel, AutoTokenizer

                model_name = "allenai/longformer-base-4096"
                logger.info(f"Loading embedding model: {model_name}")
                self._tokenizer = AutoTokenizer.from_pretrained(model_name)
                self._embedding_model = AutoModel.from_pretrained(model_name)
                self._embedding_model.eval()

                # Move to GPU if available
                if torch.cuda.is_available():
                    self._embedding_model = self._embedding_model.cuda()

            except ImportError:
                logger.error("transformers package not installed")
                raise RuntimeError(
                    "transformers package required for embedding generation. "
                    "Install with: pip install transformers"
                )
        return self._embedding_model, self._tokenizer

    def generate_embeddings(self, force: bool = False) -> torch.Tensor:
        """
        Generate embeddings for training data.

        Args:
            force: Regenerate even if embeddings exist

        Returns:
            Tensor of embeddings [num_samples, text_dim]
        """
        self._ensure_directories()

        if self.config.embeddings_path.exists() and not force:
            logger.info(f"Loading existing embeddings from {self.config.embeddings_path}")
            return torch.load(self.config.embeddings_path)

        logger.info("Generating embeddings for training data...")

        # Load training data
        if not self.config.training_data_path.exists():
            raise FileNotFoundError(
                f"Training data not found at {self.config.training_data_path}. "
                "Run data generation first."
            )

        samples = []
        with open(self.config.training_data_path) as f:
            for line in f:
                samples.append(json.loads(line))

        model, tokenizer = self._get_embedding_model()

        embeddings = []
        batch_size = 32

        with torch.no_grad():
            for i in range(0, len(samples), batch_size):
                batch = samples[i : i + batch_size]
                queries = [s["query"] for s in batch]

                # Tokenize
                inputs = tokenizer(
                    queries,
                    padding=True,
                    truncation=True,
                    max_length=512,
                    return_tensors="pt",
                )

                if torch.cuda.is_available():
                    inputs = {k: v.cuda() for k, v in inputs.items()}

                # Get embeddings (use mean pooling)
                outputs = model(**inputs)
                batch_embeddings = outputs.last_hidden_state.mean(dim=1)
                embeddings.append(batch_embeddings.cpu())

                if (i + batch_size) % 500 == 0:
                    logger.info(f"Processed {i + batch_size}/{len(samples)} samples")

        all_embeddings = torch.cat(embeddings, dim=0)
        logger.info(f"Generated {all_embeddings.shape[0]} embeddings with dim {all_embeddings.shape[1]}")

        # Save embeddings
        torch.save(all_embeddings, self.config.embeddings_path)
        logger.info(f"Saved embeddings to {self.config.embeddings_path}")

        return all_embeddings

    def write_config(self):
        """Write the YAML configuration file."""
        self._ensure_directories()

        yaml_config = self.config.to_yaml_config()

        with open(self.config.yaml_path, "w") as f:
            yaml.dump(yaml_config, f, default_flow_style=False)

        logger.info(f"Wrote config to {self.config.yaml_path}")

    def train(self, epochs: int | None = None) -> dict[str, Any]:
        """
        Train the MFRouter model.

        Args:
            epochs: Override epochs from config

        Returns:
            Training metrics dictionary
        """
        self._ensure_directories()
        self.write_config()

        # Generate embeddings if needed
        if not self.config.embeddings_path.exists():
            self.generate_embeddings()

        try:
            from llmrouter.models.mfrouter.trainer import MFRouterTrainer
        except ImportError:
            logger.error("llmrouter package not installed")
            raise RuntimeError(
                "llmrouter package required for training. "
                "Install with: pip install llmrouter"
            )

        # Change to config directory for relative paths
        original_cwd = os.getcwd()
        try:
            os.chdir(self.config.config_dir)

            trainer = MFRouterTrainer(yaml_path=str(self.config.yaml_path))

            if epochs is not None:
                trainer.config["hparam"]["epochs"] = epochs

            logger.info(f"Starting training for {epochs or self.config.epochs} epochs...")
            metrics = trainer.train()

            logger.info(f"Training complete. Model saved to {self.config.model_path}")
            return metrics

        finally:
            os.chdir(original_cwd)

    def evaluate(self) -> dict[str, float]:
        """
        Evaluate the trained model.

        Returns:
            Dictionary with accuracy metrics per tier
        """
        if not self.config.model_path.exists():
            raise FileNotFoundError(
                f"Model not found at {self.config.model_path}. Train the model first."
            )

        try:
            from llmrouter.models.mfrouter.router import MFRouter
        except ImportError:
            raise RuntimeError("llmrouter package required for evaluation")

        # Load model
        router = MFRouter(yaml_path=str(self.config.yaml_path))

        # Load test data (use training data for now, should have separate test set)
        samples = []
        with open(self.config.training_data_path) as f:
            for line in f:
                samples.append(json.loads(line))

        # Evaluate
        tier_correct = {"fast": 0, "balanced": 0, "powerful": 0}
        tier_total = {"fast": 0, "balanced": 0, "powerful": 0}

        for sample in samples:
            result = router.route_single({"query": sample["query"]})
            predicted = result.get("model_name", "balanced").lower()
            actual = sample["model_name"]

            tier_total[actual] += 1
            if predicted == actual:
                tier_correct[actual] += 1

        accuracy = {}
        for tier in tier_correct:
            if tier_total[tier] > 0:
                accuracy[tier] = tier_correct[tier] / tier_total[tier]
            else:
                accuracy[tier] = 0.0

        accuracy["overall"] = sum(tier_correct.values()) / max(sum(tier_total.values()), 1)

        logger.info(f"Evaluation results: {accuracy}")
        return accuracy

    def get_cost_analytics(self) -> dict[str, Any]:
        """
        Calculate cost analytics for the trained router.

        Returns:
            Dictionary with cost metrics and projections
        """
        cost_config = self.config.cost_per_1k_tokens

        # Calculate baseline vs routed costs
        baseline_cost = cost_config["balanced"]["input"]  # All requests at BALANCED

        # Estimated distribution after routing (from typical patterns)
        estimated_distribution = {
            "fast": 0.40,
            "balanced": 0.30,
            "powerful": 0.30,
        }

        routed_cost = sum(
            cost_config[tier]["input"] * ratio
            for tier, ratio in estimated_distribution.items()
        )

        savings_ratio = 1 - (routed_cost / baseline_cost)

        return {
            "baseline_cost_per_1k_input": baseline_cost,
            "routed_cost_per_1k_input": routed_cost,
            "estimated_savings_ratio": savings_ratio,
            "estimated_savings_percent": f"{savings_ratio * 100:.1f}%",
            "tier_distribution": estimated_distribution,
            "cost_per_tier": {
                tier: cost_config[tier]["input"] for tier in cost_config
            },
        }
