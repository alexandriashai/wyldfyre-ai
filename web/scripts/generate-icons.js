#!/usr/bin/env node
/**
 * Generate PWA icons from SVG source
 *
 * Usage: node scripts/generate-icons.js
 *
 * Requires: sharp (npm install sharp)
 */

const fs = require('fs');
const path = require('path');

async function generateIcons() {
  let sharp;
  try {
    sharp = require('sharp');
  } catch (e) {
    console.error('Sharp not installed. Run: npm install sharp --save-dev');
    console.log('\nAlternatively, use an online tool to convert the SVG:');
    console.log('1. Open public/icons/icon.svg in a browser');
    console.log('2. Use https://realfavicongenerator.net/ or similar');
    console.log('3. Download and extract icons to public/icons/');
    process.exit(1);
  }

  const svgPath = path.join(__dirname, '../public/icons/icon.svg');
  const iconsDir = path.join(__dirname, '../public/icons');
  const splashDir = path.join(__dirname, '../public/splash');

  // Ensure directories exist
  if (!fs.existsSync(iconsDir)) fs.mkdirSync(iconsDir, { recursive: true });
  if (!fs.existsSync(splashDir)) fs.mkdirSync(splashDir, { recursive: true });

  const svgBuffer = fs.readFileSync(svgPath);

  // Icon sizes for PWA
  const iconSizes = [32, 72, 96, 128, 144, 152, 180, 192, 384, 512];

  console.log('Generating PWA icons...\n');

  for (const size of iconSizes) {
    const outputPath = path.join(iconsDir, `icon-${size}x${size}.png`);
    await sharp(svgBuffer)
      .resize(size, size)
      .png()
      .toFile(outputPath);
    console.log(`  Created: icon-${size}x${size}.png`);
  }

  // Generate favicon.ico (32x32)
  const faviconPath = path.join(__dirname, '../public/favicon.ico');
  await sharp(svgBuffer)
    .resize(32, 32)
    .png()
    .toFile(faviconPath.replace('.ico', '.png'));
  console.log('  Created: favicon.png (rename to .ico or use as-is)');

  // Splash screen sizes for iOS
  const splashSizes = [
    { width: 640, height: 1136, name: 'splash-640x1136.png' },
    { width: 750, height: 1334, name: 'splash-750x1334.png' },
    { width: 1242, height: 2208, name: 'splash-1242x2208.png' },
    { width: 1125, height: 2436, name: 'splash-1125x2436.png' },
    { width: 1536, height: 2048, name: 'splash-1536x2048.png' },
  ];

  console.log('\nGenerating splash screens...\n');

  for (const { width, height, name } of splashSizes) {
    const outputPath = path.join(splashDir, name);

    // Create splash with centered icon on dark background
    const iconSize = Math.min(width, height) * 0.4;
    const iconBuffer = await sharp(svgBuffer)
      .resize(Math.round(iconSize), Math.round(iconSize))
      .png()
      .toBuffer();

    await sharp({
      create: {
        width,
        height,
        channels: 4,
        background: { r: 26, g: 22, b: 37, alpha: 1 } // #1a1625
      }
    })
      .composite([{
        input: iconBuffer,
        top: Math.round((height - iconSize) / 2),
        left: Math.round((width - iconSize) / 2),
      }])
      .png()
      .toFile(outputPath);

    console.log(`  Created: ${name}`);
  }

  console.log('\nIcon generation complete!');
  console.log('\nNote: For best results, also create:');
  console.log('  - public/og-image.png (1200x630) for social sharing');
  console.log('  - public/twitter-image.png (1200x600) for Twitter cards');
}

generateIcons().catch(console.error);
