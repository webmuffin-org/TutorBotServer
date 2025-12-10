/**
 * PDF Export Module for TutorBot Conversations
 * Uses pdfmake for client-side PDF generation
 */
const PDFExport = {
  // Colors matching conversation.css
  colors: {
    userBg: '#007bff',      // Blue for user bubbles
    userText: '#ffffff',    // White text
    botBg: '#f1f3f4',       // Light gray for bot bubbles
    botText: '#333333',     // Dark text
    botHeader: '#666666',   // Gray header text
    codeBg: '#282c34',      // Dark background for code
    codeText: '#abb2bf',    // Light text for code
    tokenInfoBg: '#e8f4f8', // Light blue for token info
    tokenInfoText: '#2c5e7a', // Dark blue text
    linkColor: '#007bff',   // Blue for links
    inlineCodeBg: '#e8e8e8', // Light gray for inline code
  },

  /**
   * Build the complete document definition for pdfmake
   */
  buildDocDefinition(data) {
    return {
      pageSize: 'LETTER',
      pageMargins: [30, 40, 30, 50],  // [left, top, right, bottom] - same for all pages
      footer: this.buildFooter(),
      content: [
        ...this.buildTitleSection(data.metadata),
        ...this.buildContent(data.messages)
      ],
      defaultStyle: { fontSize: 11, lineHeight: 1.4 },
      styles: this.getStyles(),
    };
  },

  /**
   * Build title section as content (not header) - appears only at top of first page
   */
  buildTitleSection(metadata) {
    const sessionId = metadata.session_id || 'N/A';
    const conversationId = metadata.conversation_id || 'N/A';

    return [
      // Main title
      {
        text: 'TutorBot Conversation',
        fontSize: 22,
        bold: true,
        color: '#333',
        margin: [0, 0, 0, 8]
      },
      // Class and lesson info
      {
        columns: [
          {
            text: [
              { text: 'Class: ', fontSize: 12, color: '#666' },
              { text: metadata.class_name, fontSize: 12, bold: true, color: '#333' },
            ]
          },
          {
            text: [
              { text: 'Lesson: ', fontSize: 12, color: '#666' },
              { text: metadata.lesson, fontSize: 12, bold: true, color: '#333' },
            ],
            alignment: 'right'
          }
        ],
        margin: [0, 0, 0, 4]
      },
      // Session ID (left, full) and Mode (right)
      {
        columns: [
          {
            text: [
              { text: 'Session: ', fontSize: 9, color: '#999' },
              { text: sessionId, fontSize: 9, color: '#666' },
            ]
          },
          {
            text: [
              { text: 'Mode: ', fontSize: 11, color: '#666' },
              { text: metadata.action_plan, fontSize: 11, color: '#333' },
            ],
            alignment: 'right'
          }
        ],
        margin: [0, 0, 0, 4]
      },
      // Conversation ID (left, full)
      {
        text: [
          { text: 'Conversation: ', fontSize: 9, color: '#999' },
          { text: conversationId, fontSize: 9, color: '#666' },
        ],
        margin: [0, 0, 0, 6]
      },
      // Divider line
      {
        canvas: [{
          type: 'line',
          x1: 0, y1: 0,
          x2: 552, y2: 0,  // Full width minus margins
          lineWidth: 1,
          lineColor: '#e0e0e0'
        }],
        margin: [0, 8, 0, 16]
      }
    ];
  },

  /**
   * Build page footer with page numbers and timestamp
   */
  buildFooter() {
    const timestamp = new Date().toLocaleString();
    return function(currentPage, pageCount) {
      return {
        columns: [
          {
            text: `Generated: ${timestamp}`,
            fontSize: 8,
            color: '#999',
            margin: [30, 0, 0, 0]
          },
          {
            text: `Page ${currentPage} of ${pageCount}`,
            alignment: 'right',
            fontSize: 8,
            color: '#999',
            margin: [0, 0, 30, 0]
          }
        ],
        margin: [0, 20, 0, 0]
      };
    };
  },

  /**
   * Build the main content from messages array
   */
  buildContent(messages) {
    if (!messages || messages.length === 0) {
      return [
        {
          text: 'No messages in this conversation.',
          style: 'paragraph',
          alignment: 'center',
          margin: [0, 100, 0, 0],
          color: '#999'
        }
      ];
    }

    const content = [];
    messages.forEach((message, index) => {
      if (message.role === 'user') {
        content.push(this.buildUserMessage(message.content, message.timestamp));
      } else if (message.role === 'assistant') {
        content.push(this.buildBotMessage(message.content, message.token_info, message.timestamp));
      }
      // Add spacing between messages
      if (index < messages.length - 1) {
        content.push({ text: '', margin: [0, 8, 0, 0] });
      }
    });

    return content;
  },

  /**
   * Format timestamp for display (e.g., "2:30:45 PM" or "Dec 9, 2:30:45 PM")
   */
  formatTimestamp(isoTimestamp) {
    if (!isoTimestamp) return '';
    try {
      const date = new Date(isoTimestamp);
      const now = new Date();
      const isToday = date.toDateString() === now.toDateString();

      if (isToday) {
        return date.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit', second: '2-digit' });
      }
      return date.toLocaleDateString([], { month: 'short', day: 'numeric' }) +
             ', ' + date.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit', second: '2-digit' });
    } catch (e) {
      return '';
    }
  },

  /**
   * Build a user message bubble (right-aligned, blue) with soft rounded appearance
   */
  buildUserMessage(content, timestamp) {
    const contentElements = this.parseMarkdown(content);
    const colors = this.colors;
    const formattedTime = this.formatTimestamp(timestamp);

    // Apply white text color to all content elements
    const styledElements = contentElements.map(el => {
      if (typeof el === 'string') {
        return { text: el, color: colors.userText };
      }
      // Clone and add color
      const clone = { ...el };
      if (!clone.color) {
        clone.color = colors.userText;
      }
      return clone;
    });

    return {
      table: {
        widths: ['15%', '85%'],
        body: [[
          { text: '', border: [false, false, false, false] },
          {
            stack: [
              {
                columns: [
                  { text: 'You', style: 'userHeader', width: 'auto' },
                  { text: formattedTime, fontSize: 9, color: '#cce5ff', alignment: 'right' }
                ]
              },
              ...styledElements
            ],
            fillColor: colors.userBg
          }
        ]]
      },
      layout: {
        // Add subtle border for rounded appearance effect
        hLineWidth: function(i, node) {
          return (i === 0 || i === node.table.body.length) ? 2 : 0;
        },
        vLineWidth: function(i, node) {
          return (i === 1 || i === 2) ? 2 : 0;  // Only around content cell
        },
        hLineColor: function() { return colors.userBg; },
        vLineColor: function() { return colors.userBg; },
        // Use layout padding instead of margin - this applies on EVERY page including continuations
        paddingLeft: function(i) { return i === 1 ? 12 : 0; },
        paddingRight: function(i) { return i === 1 ? 12 : 0; },
        paddingTop: function() { return 16; },
        paddingBottom: function() { return 12; }
      },
      unbreakable: false,
      // Ensure at least some content fits before starting the bubble
      dontBreakRows: true
    };
  },

  /**
   * Build a bot message bubble (left-aligned, gray) with soft rounded appearance
   */
  buildBotMessage(content, tokenInfo, timestamp) {
    const contentElements = this.parseMarkdown(content);
    const colors = this.colors;
    const formattedTime = this.formatTimestamp(timestamp);
    const stack = [
      {
        columns: [
          { text: 'TutorBot', style: 'botHeader', width: 'auto' },
          { text: formattedTime, style: 'timestamp', alignment: 'right' }
        ]
      }
    ];

    // Add token info if present
    if (tokenInfo) {
      stack.push({
        text: tokenInfo,
        style: 'tokenInfo',
        margin: [0, 4, 0, 8]
      });
    }

    // Add content elements
    stack.push(...contentElements);

    return {
      table: {
        widths: ['85%', '15%'],
        body: [[
          {
            stack: stack,
            fillColor: colors.botBg
          },
          { text: '', border: [false, false, false, false] }
        ]]
      },
      layout: {
        // Add subtle border for rounded appearance effect
        hLineWidth: function(i, node) {
          return (i === 0 || i === node.table.body.length) ? 2 : 0;
        },
        vLineWidth: function(i, node) {
          return (i === 0 || i === 1) ? 2 : 0;  // Only around content cell
        },
        hLineColor: function() { return colors.botBg; },
        vLineColor: function() { return colors.botBg; },
        // Use layout padding instead of margin - this applies on EVERY page including continuations
        paddingLeft: function(i) { return i === 0 ? 12 : 0; },
        paddingRight: function(i) { return i === 0 ? 12 : 0; },
        paddingTop: function() { return 16; },
        paddingBottom: function() { return 12; }
      },
      unbreakable: false,
      // Ensure at least some content fits before starting the bubble
      dontBreakRows: true
    };
  },

  /**
   * Parse markdown content to pdfmake content array
   */
  parseMarkdown(text) {
    if (!text) return [{ text: '', style: 'paragraph' }];

    const elements = [];
    const lines = text.split('\n');
    let i = 0;

    while (i < lines.length) {
      const line = lines[i];

      // Code blocks (```...```)
      if (line.trim().startsWith('```')) {
        const codeLines = [];
        const langMatch = line.trim().match(/^```(\w*)/);
        i++; // skip opening ```
        while (i < lines.length && !lines[i].trim().startsWith('```')) {
          codeLines.push(lines[i]);
          i++;
        }
        if (codeLines.length > 0) {
          elements.push({
            table: {
              widths: ['*'],
              body: [[{
                text: codeLines.join('\n'),
                style: 'codeBlock',
                margin: [8, 8, 8, 8]
              }]]
            },
            layout: {
              hLineWidth: function() { return 0; },
              vLineWidth: function() { return 0; },
              fillColor: function() { return '#282c34'; }
            },
            margin: [0, 6, 0, 6]
          });
        }
        i++; // skip closing ```
        continue;
      }

      // Headers (# ## ###)
      const headerMatch = line.match(/^(#{1,6})\s+(.+)$/);
      if (headerMatch) {
        const level = headerMatch[1].length;
        elements.push({
          text: this.parseInlineStyles(headerMatch[2]),
          style: `h${level}`,
          margin: [0, level === 1 ? 10 : 6, 0, 4]
        });
        i++;
        continue;
      }

      // Bullet lists (- or *)
      if (line.match(/^[\-\*]\s+/)) {
        const listItems = [];
        while (i < lines.length && lines[i].match(/^[\-\*]\s+/)) {
          const itemText = lines[i].replace(/^[\-\*]\s+/, '');
          const parsed = this.parseInlineStyles(itemText);
          // Wrap in text object to ensure inline rendering
          listItems.push(Array.isArray(parsed) ? { text: parsed } : parsed);
          i++;
        }
        elements.push({
          ul: listItems,
          margin: [0, 4, 0, 4]
        });
        continue;
      }

      // Numbered lists (1. 2. 3.)
      if (line.match(/^\d+\.\s+/)) {
        const listItems = [];
        while (i < lines.length && lines[i].match(/^\d+\.\s+/)) {
          const itemText = lines[i].replace(/^\d+\.\s+/, '');
          const parsed = this.parseInlineStyles(itemText);
          // Wrap in text object to ensure inline rendering
          listItems.push(Array.isArray(parsed) ? { text: parsed } : parsed);
          i++;
        }
        elements.push({
          ol: listItems,
          margin: [0, 4, 0, 4]
        });
        continue;
      }

      // Horizontal rule - use table-based separator to stay within bubble bounds
      if (line.match(/^[\-\*_]{3,}$/)) {
        elements.push({
          table: {
            widths: ['*'],
            body: [[{ text: '', border: [false, true, false, false], borderColor: ['', '#cccccc', '', ''] }]]
          },
          layout: {
            hLineWidth: function(i) { return i === 1 ? 0.5 : 0; },
            vLineWidth: function() { return 0; },
            hLineColor: function() { return '#cccccc'; }
          },
          margin: [0, 10, 0, 10]
        });
        i++;
        continue;
      }

      // Blockquotes
      if (line.startsWith('>')) {
        const quoteLines = [];
        while (i < lines.length && lines[i].startsWith('>')) {
          quoteLines.push(lines[i].replace(/^>\s*/, ''));
          i++;
        }
        elements.push({
          table: {
            widths: [3, '*'],
            body: [[
              { text: '', fillColor: '#007bff' },
              {
                text: this.parseInlineStyles(quoteLines.join('\n')),
                margin: [8, 4, 4, 4],
                italics: true,
                color: '#555'
              }
            ]]
          },
          layout: {
            hLineWidth: function() { return 0; },
            vLineWidth: function() { return 0; }
          },
          margin: [0, 6, 0, 6]
        });
        continue;
      }

      // Regular paragraph (non-empty lines)
      if (line.trim()) {
        elements.push({
          text: this.parseInlineStyles(line),
          style: 'paragraph',
          margin: [0, 0, 0, 4]
        });
      } else {
        // Empty line - add small spacing
        elements.push({ text: '', margin: [0, 4, 0, 0] });
      }
      i++;
    }

    return elements.length > 0 ? elements : [{ text: text, style: 'paragraph' }];
  },

  /**
   * Parse inline markdown styles: **bold**, *italic*, `code`, [links](url)
   */
  parseInlineStyles(text) {
    if (!text) return '';

    const parts = [];
    let remaining = text;

    // Combined regex to match all inline styles
    const pattern = /(\*\*(.+?)\*\*)|(\*(.+?)\*)|(`(.+?)`)|(\[(.+?)\]\((.+?)\))/g;
    let lastIndex = 0;
    let match;

    while ((match = pattern.exec(text)) !== null) {
      // Add text before the match
      if (match.index > lastIndex) {
        parts.push(text.slice(lastIndex, match.index));
      }

      if (match[1]) {
        // Bold: **text**
        parts.push({ text: match[2], bold: true });
      } else if (match[3]) {
        // Italic: *text*
        parts.push({ text: match[4], italics: true });
      } else if (match[5]) {
        // Inline code: `code`
        parts.push({
          text: ` ${match[6]} `,
          fontSize: 10,
          background: this.colors.inlineCodeBg,
          color: '#333'
        });
      } else if (match[7]) {
        // Link: [text](url)
        parts.push({
          text: match[8],
          link: match[9],
          color: this.colors.linkColor,
          decoration: 'underline'
        });
      }

      lastIndex = match.index + match[0].length;
    }

    // Add remaining text after the last match
    if (lastIndex < text.length) {
      parts.push(text.slice(lastIndex));
    }

    // If no matches found, return the original text
    return parts.length > 0 ? parts : text;
  },

  /**
   * Get style definitions
   */
  getStyles() {
    return {
      userHeader: {
        fontSize: 12,
        bold: true,
        color: this.colors.userText,
        margin: [0, 0, 0, 6]
      },
      botHeader: {
        fontSize: 12,
        bold: true,
        color: this.colors.botHeader,
        margin: [0, 0, 0, 6]
      },
      timestamp: {
        fontSize: 9,
        color: '#999999'
      },
      tokenInfo: {
        fontSize: 9,
        color: this.colors.tokenInfoText,
        fillColor: this.colors.tokenInfoBg,
        margin: [0, 0, 0, 8]
      },
      paragraph: {
        fontSize: 11,
        lineHeight: 1.4,
        color: this.colors.botText
      },
      h1: {
        fontSize: 18,
        bold: true,
        color: this.colors.botText
      },
      h2: {
        fontSize: 16,
        bold: true,
        color: this.colors.botText
      },
      h3: {
        fontSize: 14,
        bold: true,
        color: this.colors.botText
      },
      h4: {
        fontSize: 12,
        bold: true,
        color: this.colors.botText
      },
      h5: {
        fontSize: 11,
        bold: true,
        color: this.colors.botText
      },
      h6: {
        fontSize: 10,
        bold: true,
        color: this.colors.botText
      },
      codeBlock: {
        fontSize: 9,
        color: this.colors.codeText,
        preserveLeadingSpaces: true,
        lineHeight: 1.3
      },
      inlineCode: {
        fontSize: 10,
        background: this.colors.inlineCodeBg,
        color: '#333'
      },
      link: {
        color: this.colors.linkColor,
        decoration: 'underline'
      }
    };
  },

  /**
   * Generate and download the PDF
   */
  download(data) {
    const docDefinition = this.buildDocDefinition(data);
    const timestamp = new Date().toISOString().slice(0, 19).replace(/[T:]/g, '-');
    const conversationId = data.metadata.conversation_id || 'unknown';
    pdfMake.createPdf(docDefinition).download(`${timestamp}_TutorBot_${conversationId}.pdf`);
  }
};
