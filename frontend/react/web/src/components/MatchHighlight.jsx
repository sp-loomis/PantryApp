/**
 * MatchHighlight
 *
 * Renders text with the fuzzy-search match spans highlighted. `spans` are
 * whole-word character offsets `[{ start, end }]` from POST /search.
 */

import { Fragment } from 'react';
import { Box } from '@chakra-ui/react';

export default function MatchHighlight({ text, spans }) {
  if (!spans || spans.length === 0) {
    return <>{text}</>;
  }

  const sorted = [...spans].sort((a, b) => a.start - b.start);
  const parts = [];
  let cursor = 0;

  sorted.forEach((span, i) => {
    if (span.start > cursor) {
      parts.push(<Fragment key={`t${i}`}>{text.slice(cursor, span.start)}</Fragment>);
    }
    parts.push(
      <Box as="mark" key={`m${i}`} bg="yellow.200" color="inherit" borderRadius="sm" px="1px">
        {text.slice(span.start, span.end)}
      </Box>
    );
    cursor = Math.max(cursor, span.end);
  });

  if (cursor < text.length) {
    parts.push(<Fragment key="tail">{text.slice(cursor)}</Fragment>);
  }

  return <>{parts}</>;
}
