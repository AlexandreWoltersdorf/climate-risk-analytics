const fs = require('fs');
const path = require('path');
const {
  Document, Packer, Paragraph, TextRun, ImageRun, Table, TableRow, TableCell,
  Header, Footer, AlignmentType, HeadingLevel, BorderStyle, WidthType,
  ShadingType, PageNumber, PageBreak, LevelFormat,
} = require('docx');

const SHOTS = path.join(__dirname, 'screenshots');
const OUT   = path.join(__dirname, '..', 'outputs', 'website_documentation.docx');

// ── Brand colors ────────────────────────────────────────────
const BLUE   = '2525FF';
const DARK   = '18181B';
const GREY   = '71717A';
const LTGREY = 'F4F4F5';
const WHITE  = 'FFFFFF';

// ── Helper: load image ──────────────────────────────────────
function img(name, widthPx) {
  const data = fs.readFileSync(path.join(SHOTS, name));
  // Screenshots are 1440x900, scale to fit page width (approx 6.5 inches = 590px at 96dpi)
  const ratio = 900 / 1440;
  const w = widthPx || 590;
  const h = Math.round(w * ratio);
  return new ImageRun({
    type: 'png',
    data,
    transformation: { width: w, height: h },
    altText: { title: name, description: `Screenshot: ${name}`, name },
  });
}

// ── Helper: section header paragraph ────────────────────────
function sectionHeader(num, title) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    spacing: { before: 400, after: 200 },
    children: [
      new TextRun({ text: `${num}. `, color: BLUE, bold: true, font: 'Calibri', size: 36 }),
      new TextRun({ text: title, bold: true, font: 'Calibri', size: 36, color: DARK }),
    ],
  });
}

function body(text) {
  return new Paragraph({
    spacing: { after: 160 },
    children: [new TextRun({ text, font: 'Calibri', size: 22, color: GREY })],
  });
}

function bodyBold(label, text) {
  return new Paragraph({
    spacing: { after: 120 },
    children: [
      new TextRun({ text: label, font: 'Calibri', size: 22, bold: true, color: DARK }),
      new TextRun({ text, font: 'Calibri', size: 22, color: GREY }),
    ],
  });
}

function screenshot(name) {
  return new Paragraph({
    spacing: { before: 200, after: 300 },
    alignment: AlignmentType.CENTER,
    border: {
      top: { style: BorderStyle.SINGLE, size: 1, color: 'E4E4E7', space: 8 },
      bottom: { style: BorderStyle.SINGLE, size: 1, color: 'E4E4E7', space: 8 },
      left: { style: BorderStyle.SINGLE, size: 1, color: 'E4E4E7', space: 8 },
      right: { style: BorderStyle.SINGLE, size: 1, color: 'E4E4E7', space: 8 },
    },
    children: [img(name)],
  });
}

function caption(text) {
  return new Paragraph({
    spacing: { after: 300 },
    alignment: AlignmentType.CENTER,
    children: [new TextRun({ text, font: 'Calibri', size: 18, italics: true, color: GREY })],
  });
}

function spacer() {
  return new Paragraph({ spacing: { after: 100 }, children: [] });
}

// ── Spec table helper ───────────────────────────────────────
const border = { style: BorderStyle.SINGLE, size: 1, color: 'E4E4E7' };
const borders = { top: border, bottom: border, left: border, right: border };
const cellMargins = { top: 80, bottom: 80, left: 120, right: 120 };

function specRow(label, value, isHeader) {
  const fill = isHeader ? DARK : WHITE;
  const textColor = isHeader ? WHITE : DARK;
  const valueColor = isHeader ? WHITE : GREY;
  return new TableRow({
    children: [
      new TableCell({
        borders, width: { size: 3200, type: WidthType.DXA },
        shading: { fill, type: ShadingType.CLEAR },
        margins: cellMargins,
        children: [new Paragraph({ children: [new TextRun({ text: label, font: 'Calibri', size: 20, bold: true, color: textColor })] })],
      }),
      new TableCell({
        borders, width: { size: 6160, type: WidthType.DXA },
        shading: { fill, type: ShadingType.CLEAR },
        margins: cellMargins,
        children: [new Paragraph({ children: [new TextRun({ text: value, font: 'Calibri', size: 20, color: valueColor })] })],
      }),
    ],
  });
}

// ── Build document ──────────────────────────────────────────
const doc = new Document({
  styles: {
    default: {
      document: { run: { font: 'Calibri', size: 22 } },
    },
    paragraphStyles: [
      {
        id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: 36, bold: true, font: 'Calibri', color: DARK },
        paragraph: { spacing: { before: 400, after: 200 }, outlineLevel: 0 },
      },
      {
        id: 'Heading2', name: 'Heading 2', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: 28, bold: true, font: 'Calibri', color: DARK },
        paragraph: { spacing: { before: 300, after: 160 }, outlineLevel: 1 },
      },
    ],
  },
  numbering: {
    config: [
      {
        reference: 'bullets',
        levels: [{
          level: 0, format: LevelFormat.BULLET, text: '\u2022', alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } },
        }],
      },
    ],
  },
  sections: [
    // ──────────────────────────────────────────────────────────
    // COVER PAGE
    // ──────────────────────────────────────────────────────────
    {
      properties: {
        page: {
          size: { width: 12240, height: 15840 },
          margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 },
        },
      },
      children: [
        new Paragraph({ spacing: { before: 3600 }, children: [] }),
        new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { after: 200 },
          children: [new TextRun({ text: 'OPEN CLIMATE RISK', font: 'Calibri', size: 20, bold: true, color: BLUE, characterSpacing: 300 })],
        }),
        new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { after: 100 },
          children: [new TextRun({ text: 'Website Documentation', font: 'Calibri Light', size: 56, color: DARK })],
        }),
        new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { after: 600 },
          children: [new TextRun({ text: 'Architecture, Visual Design & Page Structure', font: 'Calibri Light', size: 28, color: GREY })],
        }),
        new Paragraph({
          alignment: AlignmentType.CENTER,
          border: { top: { style: BorderStyle.SINGLE, size: 2, color: BLUE, space: 16 } },
          spacing: { before: 400 },
          children: [new TextRun({ text: 'Version 1.0  |  March 2026', font: 'Calibri', size: 22, color: GREY })],
        }),
        new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { after: 200 },
          children: [new TextRun({ text: 'http://localhost:8080', font: 'Calibri', size: 20, color: BLUE })],
        }),
      ],
    },

    // ──────────────────────────────────────────────────────────
    // TABLE OF CONTENTS (manual)
    // ──────────────────────────────────────────────────────────
    {
      properties: {
        page: {
          size: { width: 12240, height: 15840 },
          margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 },
        },
      },
      headers: {
        default: new Header({
          children: [new Paragraph({
            border: { bottom: { style: BorderStyle.SINGLE, size: 1, color: 'E4E4E7', space: 4 } },
            children: [
              new TextRun({ text: 'Open Climate Risk', font: 'Calibri', size: 18, color: BLUE, bold: true }),
              new TextRun({ text: '  |  Website Documentation', font: 'Calibri', size: 18, color: GREY }),
            ],
          })],
        }),
      },
      footers: {
        default: new Footer({
          children: [new Paragraph({
            alignment: AlignmentType.RIGHT,
            children: [
              new TextRun({ text: 'Page ', font: 'Calibri', size: 18, color: GREY }),
              new TextRun({ children: [PageNumber.CURRENT], font: 'Calibri', size: 18, color: GREY }),
            ],
          })],
        }),
      },
      children: [
        new Paragraph({
          spacing: { after: 400 },
          children: [new TextRun({ text: 'Table of Contents', font: 'Calibri Light', size: 40, color: DARK })],
        }),
        ...[
          ['1', 'Overview'],
          ['2', 'Technical Specifications'],
          ['3', 'Site Map & Information Architecture'],
          ['4', 'Section 1 — Hero'],
          ['5', 'Section 2 — Key Metrics'],
          ['6', 'Section 3 — Features'],
          ['7', 'Section 4 — Pipeline'],
          ['8', 'Section 5 — Architecture'],
          ['9', 'Section 6 — Data Sources'],
          ['10', 'Section 7 — Hazard Modules'],
          ['11', 'Section 8 — Roadmap'],
          ['12', 'Section 9 — References'],
          ['13', 'Section 10 — Call to Action & Footer'],
          ['14', 'Design System'],
        ].map(([num, title]) => new Paragraph({
          spacing: { after: 160 },
          border: { bottom: { style: BorderStyle.DOTTED, size: 1, color: 'E4E4E7', space: 4 } },
          children: [
            new TextRun({ text: `${num}.  `, font: 'Calibri', size: 22, color: BLUE, bold: true }),
            new TextRun({ text: title, font: 'Calibri', size: 22, color: DARK }),
          ],
        })),
      ],
    },

    // ──────────────────────────────────────────────────────────
    // 1. OVERVIEW
    // ──────────────────────────────────────────────────────────
    {
      properties: {
        page: {
          size: { width: 12240, height: 15840 },
          margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 },
        },
      },
      headers: {
        default: new Header({
          children: [new Paragraph({
            border: { bottom: { style: BorderStyle.SINGLE, size: 1, color: 'E4E4E7', space: 4 } },
            children: [
              new TextRun({ text: 'Open Climate Risk', font: 'Calibri', size: 18, color: BLUE, bold: true }),
              new TextRun({ text: '  |  Website Documentation', font: 'Calibri', size: 18, color: GREY }),
            ],
          })],
        }),
      },
      footers: {
        default: new Footer({
          children: [new Paragraph({
            alignment: AlignmentType.RIGHT,
            children: [
              new TextRun({ text: 'Page ', font: 'Calibri', size: 18, color: GREY }),
              new TextRun({ children: [PageNumber.CURRENT], font: 'Calibri', size: 18, color: GREY }),
            ],
          })],
        }),
      },
      children: [
        sectionHeader('1', 'Overview'),
        body('This document provides a comprehensive overview of the Open Climate Risk Platform website. It details the visual design, page architecture, section structure, and design system used throughout the site.'),
        body('The website is a single-page application (SPA) built with vanilla HTML, CSS, and JavaScript. It presents the Open Climate Risk Platform \u2014 an open-source Python toolkit for physical climate risk screening using public datasets.'),
        spacer(),
        new Paragraph({
          heading: HeadingLevel.HEADING_2,
          children: [new TextRun({ text: 'Purpose', bold: true, font: 'Calibri', size: 28, color: DARK })],
        }),
        ...[
          'Present the project value proposition and capabilities',
          'Explain the 4-stage risk computation pipeline',
          'Document the modular Python package architecture',
          'Showcase multi-hazard coverage and roadmap',
          'Provide scientific references and credibility',
          'Drive users to the GitHub repository for installation',
        ].map(t => new Paragraph({
          numbering: { reference: 'bullets', level: 0 },
          spacing: { after: 80 },
          children: [new TextRun({ text: t, font: 'Calibri', size: 22, color: GREY })],
        })),

        // ──── 2. TECH SPECS ────
        new Paragraph({ children: [new PageBreak()] }),
        sectionHeader('2', 'Technical Specifications'),
        new Table({
          width: { size: 9360, type: WidthType.DXA },
          columnWidths: [3200, 6160],
          rows: [
            specRow('Property', 'Value', true),
            specRow('Type', 'Single-page static website'),
            specRow('Framework', 'Vanilla HTML5 / CSS3 / JavaScript'),
            specRow('Fonts', 'Inter (Google Fonts), JetBrains Mono'),
            specRow('Responsive', 'Yes \u2014 breakpoints at 900px and 600px'),
            specRow('Animations', 'Intersection Observer fade-in on scroll'),
            specRow('Navigation', 'Fixed glassmorphic navbar with backdrop-filter blur'),
            specRow('Total sections', '10 content sections + nav + footer'),
            specRow('External deps', 'Google Fonts CDN only'),
            specRow('File size', 'Single index.html (~28 KB)'),
            specRow('Hosting', 'Any static server (python -m http.server)'),
            specRow('Brand colors', '#2525FF (OCR Blue), #18181B (Dark), #F4F4F5 (BG)'),
          ],
        }),

        // ──── 3. SITE MAP ────
        new Paragraph({ children: [new PageBreak()] }),
        sectionHeader('3', 'Site Map & Information Architecture'),
        body('The website follows a linear narrative structure, guiding the user from value proposition through technical details to action. Each section is accessible via anchor links in the navigation bar.'),
        spacer(),
        new Table({
          width: { size: 9360, type: WidthType.DXA },
          columnWidths: [600, 2200, 3000, 3560],
          rows: [
            new TableRow({
              children: ['#', 'Section', 'Content', 'Visual Style'].map(h =>
                new TableCell({
                  borders, width: { size: h === '#' ? 600 : h === 'Section' ? 2200 : h === 'Content' ? 3000 : 3560, type: WidthType.DXA },
                  shading: { fill: DARK, type: ShadingType.CLEAR },
                  margins: cellMargins,
                  children: [new Paragraph({ children: [new TextRun({ text: h, font: 'Calibri', size: 18, bold: true, color: WHITE })] })],
                })
              ),
            }),
            ...([
              ['1', 'Hero', 'Tagline, CTA buttons, pip install, terminal mockup', 'Gradient BG, 2-col grid'],
              ['2', 'Stats Bar', '4 key metrics (135 GeoTIFFs, 5 GCMs, 9 RPs, 100% open)', 'White, centered numbers'],
              ['3', 'Features', '6 capability cards with icons', 'Grey BG, 3-col grid cards'],
              ['4', 'Pipeline', '4-step flow: Asset \u2192 Hazard \u2192 Damage \u2192 EAD', 'White, numbered circles'],
              ['5', 'Architecture', 'File tree + 5 module cards', 'Grey BG, dark terminal + cards'],
              ['6', 'Data Sources', 'Table: datasets, resolution, license', 'White, styled table'],
              ['7', 'Hazard Modules', '6 hazard cards with status badges', 'Grey BG, 2-col grid'],
              ['8', 'Roadmap', '5-item timeline (Now \u2192 2027)', 'White, vertical timeline'],
              ['9', 'References', '5 peer-reviewed papers with DOIs', 'Grey BG, stacked cards'],
              ['10', 'CTA + Footer', 'Git clone instructions, GitHub link', 'Dark BG, terminal block'],
            ].map(([num, section, content, style]) =>
              new TableRow({
                children: [
                  [num, 600], [section, 2200], [content, 3000], [style, 3560],
                ].map(([text, w]) =>
                  new TableCell({
                    borders, width: { size: w, type: WidthType.DXA },
                    shading: { fill: WHITE, type: ShadingType.CLEAR },
                    margins: cellMargins,
                    children: [new Paragraph({ children: [new TextRun({ text, font: 'Calibri', size: 18, color: num === num ? DARK : GREY })] })],
                  })
                ),
              })
            )),
          ],
        }),

        // ──── SECTION PAGES ────
        // 4. Hero
        new Paragraph({ children: [new PageBreak()] }),
        sectionHeader('4', 'Section 1 \u2014 Hero'),
        body('The hero is the first viewport visitors see. It uses a two-column grid layout: the left column contains the value proposition, CTA buttons, and a pip install command; the right column shows a terminal mockup with a realistic code example.'),
        bodyBold('Background: ', 'Subtle gradient from white to blue-05 (#EDEDFF) with decorative concentric circle borders.'),
        bodyBold('Badge: ', 'Version pill (v0.1) with "Open-source climate risk screening" label.'),
        bodyBold('Terminal: ', 'Dark rounded card with macOS-style traffic lights, showing Python code with syntax highlighting.'),
        screenshot('01_hero.png'),
        caption('Figure 1 \u2014 Hero section at 1440px viewport width'),

        // 5. Stats
        new Paragraph({ children: [new PageBreak()] }),
        sectionHeader('5', 'Section 2 \u2014 Key Metrics'),
        body('A compact stats bar immediately below the hero. Four key numbers communicate scale and credibility at a glance. Uses large blue numbers (#2525FF) with grey descriptive labels.'),
        bodyBold('Layout: ', '4-column grid, centered text, white background with bottom border.'),
        screenshot('02_stats.png'),
        caption('Figure 2 \u2014 Stats bar section'),

        // 6. Features
        new Paragraph({ children: [new PageBreak()] }),
        sectionHeader('6', 'Section 3 \u2014 Features'),
        body('Six feature cards in a 3-column grid, each with a colored icon container, title, and description. Cards have a white background, subtle border, and hover effect (border turns blue, slight elevation, upward translate).'),
        bodyBold('Cards: ', 'Hazard Extraction, Vulnerability Curves, Expected Annual Damage, Climate Scenarios, Portfolio Analysis, Automated Reports.'),
        bodyBold('Icons: ', 'SVG icons in colored rounded containers matching each feature\u2019s theme.'),
        screenshot('03_features.png'),
        caption('Figure 3 \u2014 Features section with 6 capability cards'),

        // 7. Pipeline
        new Paragraph({ children: [new PageBreak()] }),
        sectionHeader('7', 'Section 4 \u2014 Pipeline'),
        body('A four-step horizontal flow showing the risk computation pipeline. Each step has a numbered circle connected by horizontal lines, a title, and a short description.'),
        bodyBold('Steps: ', '1. Define Asset \u2192 2. Extract Hazard \u2192 3. Apply Damage \u2192 4. Compute EAD'),
        bodyBold('Visual: ', 'Blue circle numbers with blue-05 background, connected by blue-40 lines. Responsive: stacks to 2-col then 1-col.'),
        screenshot('04_pipeline.png'),
        caption('Figure 4 \u2014 Four-stage risk pipeline'),

        // 8. Architecture
        new Paragraph({ children: [new PageBreak()] }),
        sectionHeader('8', 'Section 5 \u2014 Architecture'),
        body('Two-column layout: left side shows a dark terminal-style file tree of the Python package; right side shows five module cards with colored left-accent borders.'),
        bodyBold('File tree: ', 'Dark background (#18181B), monospace font, directories in blue-40, files in grey, comments in dark grey.'),
        bodyBold('Module cards: ', 'White with left accent bar: blue (config), orange (data), red (analysis), green (plot), teal (report).'),
        screenshot('05_architecture.png'),
        caption('Figure 5 \u2014 Package architecture: file tree + module cards'),

        // 9. Data Sources
        new Paragraph({ children: [new PageBreak()] }),
        sectionHeader('9', 'Section 6 \u2014 Data Sources'),
        body('A clean HTML table listing the four data sources: Riverine Hazard (WRI Aqueduct v2), Coastal Hazard, Vulnerability (JRC), and Climate Models (ISIMIP2b). Each row shows dataset, resolution, coverage, and license badge.'),
        bodyBold('License badges: ', 'Green rounded pills ("CC BY 4.0", "Public domain").'),
        bodyBold('Hover effect: ', 'Row highlights with blue-05 background.'),
        screenshot('06_data.png'),
        caption('Figure 6 \u2014 Data sources table'),

        // 10. Hazards
        new Paragraph({ children: [new PageBreak()] }),
        sectionHeader('10', 'Section 7 \u2014 Hazard Modules'),
        body('Six hazard cards in a 2-column grid. Each card shows an SVG icon, hazard name, description, and a status badge indicating implementation status.'),
        bodyBold('Live (green): ', 'Riverine Flood, Coastal Flood \u2014 currently implemented.'),
        bodyBold('Next (amber): ', 'Heat Stress \u2014 planned for Q3 2026.'),
        bodyBold('Planned (blue): ', 'Wildfire, Drought, Wind/Cyclone \u2014 2027+.'),
        screenshot('07_hazards.png'),
        caption('Figure 7 \u2014 Multi-hazard coverage with status badges'),

        // 11. Roadmap
        new Paragraph({ children: [new PageBreak()] }),
        sectionHeader('11', 'Section 8 \u2014 Roadmap'),
        body('A vertical timeline with 5 milestones from Now through 2027. Each item has a dot on the timeline axis (filled for current, outlined for future), a date label in blue, title, and description.'),
        bodyBold('Timeline: ', 'Vertical blue-15 line with positioned dots. Active dot is filled blue, future dots are outlined.'),
        screenshot('08_roadmap.png'),
        caption('Figure 8 \u2014 Development roadmap timeline'),

        // 12. References
        new Paragraph({ children: [new PageBreak()] }),
        sectionHeader('12', 'Section 9 \u2014 References'),
        body('Five peer-reviewed reference cards stacked vertically. Each contains author, year, title, journal, and DOI link. Clean white cards with grey border on grey-bg background.'),
        screenshot('09_references.png'),
        caption('Figure 9 \u2014 Scientific references section'),

        // 13. CTA + Footer
        new Paragraph({ children: [new PageBreak()] }),
        sectionHeader('13', 'Section 10 \u2014 Call to Action & Footer'),
        body('Dark section (#18181B) with a radial blue glow background effect. Contains the "Start screening climate risk in five minutes" headline, a terminal block with git clone commands, and a "View on GitHub" CTA button.'),
        bodyBold('Footer: ', 'Minimal dark footer with logo, "MIT License" text, and navigation links (GitHub, Documentation, PyPI, Contact).'),
        screenshot('10_cta.png'),
        caption('Figure 10 \u2014 Call to action and footer'),

        // ──── 14. DESIGN SYSTEM ────
        new Paragraph({ children: [new PageBreak()] }),
        sectionHeader('14', 'Design System'),
        new Paragraph({
          heading: HeadingLevel.HEADING_2,
          spacing: { before: 200, after: 160 },
          children: [new TextRun({ text: 'Color Palette', bold: true, font: 'Calibri', size: 28, color: DARK })],
        }),
        new Table({
          width: { size: 9360, type: WidthType.DXA },
          columnWidths: [2000, 2000, 2680, 2680],
          rows: [
            new TableRow({
              children: ['Swatch', 'Name', 'Hex', 'Usage'].map((h, i) =>
                new TableCell({
                  borders, width: { size: [2000,2000,2680,2680][i], type: WidthType.DXA },
                  shading: { fill: DARK, type: ShadingType.CLEAR },
                  margins: cellMargins,
                  children: [new Paragraph({ children: [new TextRun({ text: h, font: 'Calibri', size: 18, bold: true, color: WHITE })] })],
                })
              ),
            }),
            ...([
              [BLUE, 'OCR Blue', '#2525FF', 'Primary, links, accents, CTAs'],
              ['5858FF', 'Blue 70', '#5858FF', 'Hover states'],
              ['8F8FFF', 'Blue 40', '#8F8FFF', 'Decorative borders'],
              ['C9C9FF', 'Blue 15', '#C9C9FF', 'Timeline, subtle borders'],
              ['EDEDFF', 'Blue 05', '#EDEDFF', 'Hero gradient, hover bg'],
              [DARK, 'Dark', '#18181B', 'Headings, terminal bg, CTA bg'],
              [GREY, 'Grey Text', '#71717A', 'Body text, descriptions'],
              ['E4E4E7', 'Grey Border', '#E4E4E7', 'Card borders, dividers'],
              ['F4F4F5', 'Grey BG', '#F4F4F5', 'Alternating section bg'],
              ['FF8C00', 'Orange', '#FF8C00', 'Data module accent'],
              ['E63946', 'Red', '#E63946', 'Analysis module accent'],
              ['00B87A', 'Green', '#00B87A', 'Badges, terminal prompt'],
              ['0096B4', 'Teal', '#0096B4', 'Report module accent'],
            ].map(([fill, name, hex, usage]) =>
              new TableRow({
                children: [
                  new TableCell({
                    borders, width: { size: 2000, type: WidthType.DXA }, margins: cellMargins,
                    children: [new Paragraph({
                      children: [new TextRun({ text: '\u2588\u2588\u2588\u2588', font: 'Calibri', size: 28, color: fill })],
                    })],
                  }),
                  ...[
                    [name, 2000, DARK], [hex, 2680, BLUE], [usage, 2680, GREY],
                  ].map(([text, w, color]) =>
                    new TableCell({
                      borders, width: { size: w, type: WidthType.DXA }, margins: cellMargins,
                      children: [new Paragraph({ children: [new TextRun({ text, font: 'Calibri', size: 18, color })] })],
                    })
                  ),
                ],
              })
            )),
          ],
        }),

        spacer(),
        new Paragraph({
          heading: HeadingLevel.HEADING_2,
          spacing: { before: 300, after: 160 },
          children: [new TextRun({ text: 'Typography', bold: true, font: 'Calibri', size: 28, color: DARK })],
        }),
        new Table({
          width: { size: 9360, type: WidthType.DXA },
          columnWidths: [2400, 2400, 2280, 2280],
          rows: [
            new TableRow({
              children: ['Element', 'Font', 'Weight', 'Size'].map((h, i) =>
                new TableCell({
                  borders, width: { size: [2400,2400,2280,2280][i], type: WidthType.DXA },
                  shading: { fill: DARK, type: ShadingType.CLEAR },
                  margins: cellMargins,
                  children: [new Paragraph({ children: [new TextRun({ text: h, font: 'Calibri', size: 18, bold: true, color: WHITE })] })],
                })
              ),
            }),
            ...([
              ['Hero heading', 'Inter', '800 (ExtraBold)', '3.5rem (56px)'],
              ['Section title', 'Inter', '800 (ExtraBold)', '2.5rem (40px)'],
              ['Card title', 'Inter', '700 (Bold)', '1.1rem (17.6px)'],
              ['Body text', 'Inter', '400 (Regular)', '0.9rem (14.4px)'],
              ['Nav links', 'Inter', '500 (Medium)', '0.9rem (14.4px)'],
              ['Code / terminal', 'JetBrains Mono', '400 (Regular)', '0.82rem (13px)'],
              ['Section label', 'Inter', '700 (Bold)', '0.75rem (12px)'],
              ['Badge / status', 'Inter', '700 (Bold)', '0.7rem (11.2px)'],
            ].map(([el, font, weight, size]) =>
              new TableRow({
                children: [
                  [el, 2400, DARK], [font, 2400, GREY], [weight, 2280, GREY], [size, 2280, GREY],
                ].map(([text, w, color]) =>
                  new TableCell({
                    borders, width: { size: w, type: WidthType.DXA }, margins: cellMargins,
                    children: [new Paragraph({ children: [new TextRun({ text, font: 'Calibri', size: 18, color })] })],
                  })
                ),
              })
            )),
          ],
        }),

        spacer(),
        new Paragraph({
          heading: HeadingLevel.HEADING_2,
          spacing: { before: 300, after: 160 },
          children: [new TextRun({ text: 'UI Components', bold: true, font: 'Calibri', size: 28, color: DARK })],
        }),
        ...([
          ['Feature cards', 'White bg, 1px grey border, 16px border-radius. On hover: blue border, 8px box-shadow (rgba blue 8%), -2px translateY.'],
          ['Section labels', 'Uppercase, 0.75rem, bold, 0.1em letter-spacing, OCR Blue color.'],
          ['Buttons (primary)', 'Blue bg (#2525FF), white text, 10px border-radius, 14px 28px padding, 600 weight. Hover: Blue-70 (#5858FF).'],
          ['Buttons (secondary)', 'White bg, grey border, 10px border-radius. Hover: blue-40 border.'],
          ['Terminal mockup', 'Dark bg (#18181B), 16px border-radius, header bar (#27272A) with 3 traffic-light dots, monospace content with syntax-highlighted code.'],
          ['Status badges', 'Rounded pill (100px radius), uppercase text, colored bg: green (#DCFCE7), amber (#FEF3C7), blue (#EDEDFF).'],
          ['Data table', 'Dark header row, white body rows, grey borders, green license badges. Row hover highlights in blue-05.'],
          ['Navigation', 'Fixed position, white bg with 85% opacity, 20px backdrop-filter blur. Adds shadow on scroll via JS class toggle.'],
          ['Scroll animations', 'Elements with .fade-in class start at opacity:0, translateY:24px. IntersectionObserver adds .visible class at 10% threshold.'],
        ]).map(([label, desc]) => bodyBold(`${label}: `, desc)),
      ],
    },
  ],
});

// ── Write ───────────────────────────────────────────────────
Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync(OUT, buffer);
  console.log(`Saved -> ${OUT}`);
  console.log(`Size: ${(buffer.length / 1024).toFixed(0)} KB`);
});
