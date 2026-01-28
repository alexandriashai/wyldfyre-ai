#!/usr/bin/env python3
"""
ContentRouter Training CLI.

Usage:
    python scripts/train_content_router.py generate --samples 10000
    python scripts/train_content_router.py train --epochs 50
    python scripts/train_content_router.py evaluate
    python scripts/train_content_router.py full
    python scripts/train_content_router.py analytics
"""

import argparse
import json
import sys
from pathlib import Path

# Add packages to path
sys.path.insert(0, str(Path(__file__).parent.parent / "packages" / "core" / "src"))

from ai_core.router_training import (
    RouterTrainer,
    TrainingConfig,
    generate_training_data,
)


def cmd_generate(args):
    """Generate synthetic training data."""
    config = TrainingConfig(config_dir=args.config_dir)

    print(f"Generating {args.samples} training samples...")
    print(f"  Tier distribution: 40% FAST, 30% BALANCED, 30% POWERFUL")

    samples = generate_training_data(
        num_samples=args.samples,
        output_path=config.training_data_path,
        seed=args.seed,
    )

    print(f"  Generated {len(samples)} samples")
    print(f"  Saved to: {config.training_data_path}")

    # Show sample distribution
    tier_counts = {}
    for sample in samples:
        tier = sample["model_name"]
        tier_counts[tier] = tier_counts.get(tier, 0) + 1

    print("\n  Distribution:")
    for tier, count in sorted(tier_counts.items()):
        pct = count / len(samples) * 100
        print(f"    {tier}: {count} ({pct:.1f}%)")


def cmd_train(args):
    """Train the MFRouter model."""
    config = TrainingConfig(
        config_dir=args.config_dir,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.lr,
    )
    trainer = RouterTrainer(config)

    print(f"Training MFRouter model...")
    print(f"  Config dir: {config.config_dir}")
    print(f"  Epochs: {config.epochs}")
    print(f"  Batch size: {config.batch_size}")
    print(f"  Learning rate: {config.learning_rate}")

    # Generate embeddings if needed
    if not config.embeddings_path.exists():
        print("\nGenerating embeddings (this may take a while)...")
        trainer.generate_embeddings()
    else:
        print(f"\n  Using existing embeddings: {config.embeddings_path}")

    # Train
    print("\nStarting training...")
    try:
        metrics = trainer.train(epochs=args.epochs)
        print(f"\nTraining complete!")
        print(f"  Model saved to: {config.model_path}")
        if metrics:
            print(f"  Final metrics: {json.dumps(metrics, indent=2)}")
    except Exception as e:
        print(f"\nTraining failed: {e}")
        print("\nNote: Ensure llmrouter is installed: pip install llmrouter")
        return 1


def cmd_evaluate(args):
    """Evaluate the trained model."""
    config = TrainingConfig(config_dir=args.config_dir)
    trainer = RouterTrainer(config)

    print("Evaluating MFRouter model...")
    print(f"  Model path: {config.model_path}")

    try:
        accuracy = trainer.evaluate()

        print("\nAccuracy by tier:")
        for tier, acc in sorted(accuracy.items()):
            pct = acc * 100
            status = "OK" if pct >= 85 else "LOW"
            print(f"  {tier}: {pct:.1f}% [{status}]")

        if accuracy.get("overall", 0) < 0.85:
            print("\nWarning: Overall accuracy below 85%. Consider:")
            print("  - Generating more training data")
            print("  - Increasing training epochs")
            print("  - Adjusting tier templates")
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1
    except Exception as e:
        print(f"Evaluation failed: {e}")
        print("\nNote: Ensure llmrouter is installed: pip install llmrouter")
        return 1


def cmd_full(args):
    """Run full training pipeline: generate -> train -> evaluate."""
    print("=" * 60)
    print("Full Training Pipeline")
    print("=" * 60)

    print("\n[1/3] Generating training data...")
    cmd_generate(args)

    print("\n[2/3] Training model...")
    result = cmd_train(args)
    if result:
        return result

    print("\n[3/3] Evaluating model...")
    cmd_evaluate(args)

    print("\n" + "=" * 60)
    print("Pipeline complete!")
    print("=" * 60)


def cmd_analytics(args):
    """Display cost analytics for the router."""
    config = TrainingConfig(config_dir=args.config_dir)
    trainer = RouterTrainer(config)

    print("Cost Analytics for ContentRouter")
    print("=" * 50)

    analytics = trainer.get_cost_analytics()

    print("\nCost per 1K input tokens by tier:")
    for tier, cost in analytics["cost_per_tier"].items():
        print(f"  {tier}: ${cost:.5f}")

    print(f"\nBaseline cost (all BALANCED): ${analytics['baseline_cost_per_1k_input']:.5f}/1K tokens")
    print(f"Routed cost (with router): ${analytics['routed_cost_per_1k_input']:.5f}/1K tokens")

    print(f"\nEstimated savings: {analytics['estimated_savings_percent']}")

    print("\nEstimated tier distribution after routing:")
    for tier, ratio in analytics["tier_distribution"].items():
        print(f"  {tier}: {ratio * 100:.0f}%")

    print("\nNote: Actual savings depend on your query distribution.")


def cmd_embeddings(args):
    """Generate embeddings only."""
    config = TrainingConfig(config_dir=args.config_dir)
    trainer = RouterTrainer(config)

    print("Generating embeddings...")
    print(f"  Training data: {config.training_data_path}")
    print(f"  Output: {config.embeddings_path}")

    trainer.generate_embeddings(force=args.force)
    print("Done!")


def main():
    parser = argparse.ArgumentParser(
        description="ContentRouter Training CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate 10,000 training samples
  python train_content_router.py generate --samples 10000

  # Train the model for 50 epochs
  python train_content_router.py train --epochs 50

  # Evaluate model accuracy
  python train_content_router.py evaluate

  # Run full pipeline
  python train_content_router.py full

  # View cost analytics
  python train_content_router.py analytics
        """,
    )
    parser.add_argument(
        "--config-dir",
        default="/home/wyld-core/config/router",
        help="Router configuration directory",
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Generate command
    gen_parser = subparsers.add_parser("generate", help="Generate training data")
    gen_parser.add_argument(
        "--samples", type=int, default=10000, help="Number of samples to generate"
    )
    gen_parser.add_argument(
        "--seed", type=int, default=None, help="Random seed for reproducibility"
    )

    # Train command
    train_parser = subparsers.add_parser("train", help="Train the router model")
    train_parser.add_argument(
        "--epochs", type=int, default=50, help="Number of training epochs"
    )
    train_parser.add_argument(
        "--batch-size", type=int, default=32, help="Training batch size"
    )
    train_parser.add_argument(
        "--lr", type=float, default=0.001, help="Learning rate"
    )

    # Evaluate command
    subparsers.add_parser("evaluate", help="Evaluate the trained model")

    # Full pipeline command
    full_parser = subparsers.add_parser("full", help="Run full training pipeline")
    full_parser.add_argument(
        "--samples", type=int, default=10000, help="Number of samples to generate"
    )
    full_parser.add_argument("--seed", type=int, default=42, help="Random seed")
    full_parser.add_argument(
        "--epochs", type=int, default=50, help="Number of training epochs"
    )
    full_parser.add_argument(
        "--batch-size", type=int, default=32, help="Training batch size"
    )
    full_parser.add_argument(
        "--lr", type=float, default=0.001, help="Learning rate"
    )

    # Analytics command
    subparsers.add_parser("analytics", help="Display cost analytics")

    # Embeddings command
    emb_parser = subparsers.add_parser("embeddings", help="Generate embeddings only")
    emb_parser.add_argument(
        "--force", action="store_true", help="Regenerate even if exists"
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    commands = {
        "generate": cmd_generate,
        "train": cmd_train,
        "evaluate": cmd_evaluate,
        "full": cmd_full,
        "analytics": cmd_analytics,
        "embeddings": cmd_embeddings,
    }

    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main() or 0)
