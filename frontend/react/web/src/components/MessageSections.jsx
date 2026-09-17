/**
 * MessageSections — renders a message's rendered section snapshots.
 *
 * A message stores an ordered list of sections, each a snapshot taken when the
 * report ran: `{ type, heading, content }`. This component knows how to display
 * each v1 section type (custom_message, task_query, item_query). Unknown types
 * fall back to a JSON dump so nothing is silently dropped.
 */

import { Box, Heading, Link, Table, Tbody, Td, Text, Tr, Wrap, WrapItem } from '@chakra-ui/react';
import { Link as RouterLink } from 'react-router-dom';

import { formatDate } from '../utils/dates';

/** Trim trailing zeros off an aggregate value for display (mirrors slack_blocks). */
function formatTotal(value) {
  const num = Number(value);
  if (Number.isNaN(num)) return String(value);
  return Number(num.toFixed(2)).toString();
}

/**
 * Per-category aggregate rollup shown under an item_query table. Mirrors the
 * Slack `📊` context line so the message log and Slack read the same.
 */
function CategoryTotals({ totals }) {
  if (!totals || totals.length === 0) return null;
  return (
    <Wrap mt={2} spacing={3} fontSize="sm">
      {totals.map((t) => (
        <WrapItem key={t.category_id} color="gray.600">
          📊 <Text as="span" fontWeight="semibold" ml={1}>{t.name}</Text>
          <Text as="span" ml={1}>
            {formatTotal(t.value)} {t.unit}
          </Text>
        </WrapItem>
      ))}
    </Wrap>
  );
}

// Mirrors backend STATUS_EMOJI (slack_blocks.py) so task rows read the same in
// both the message log and Slack.
const STATUS_EMOJI = {
  overdue: '⚠️',
  due_today: '📅',
  due_soon: '🕐',
  done: '✅',
};
const DEFAULT_BULLET = '•';

function TextContent({ content }) {
  return <Text whiteSpace="pre-wrap">{content?.text || ''}</Text>;
}

/**
 * Task/item sections render as a two-column table: name (deep link) + due date,
 * with a leading status-emoji column. `isTask` picks the id, route, date field,
 * emoji, and date label for the row.
 */
function ItemsTable({ content, emptyLabel, isTask }) {
  const items = content?.items || [];
  if (items.length === 0) {
    return (
      <Text color="gray.500" fontSize="sm">
        {emptyLabel}
      </Text>
    );
  }
  return (
    <Table size="sm" variant="unstyled">
      <Tbody>
        {items.map((item) => {
          const id = isTask ? item.task_id : item.item_id;
          const to = isTask ? `/tasks/${id}` : `/items/${id}`;
          const emoji = isTask
            ? STATUS_EMOJI[item.computed_status] || DEFAULT_BULLET
            : DEFAULT_BULLET;
          const due = formatDate(isTask ? item.current_due : item.use_by_date);
          return (
            <Tr key={id} fontSize="sm">
              <Td px={0} py={1} width="1.5em" verticalAlign="top">
                {emoji}
              </Td>
              <Td px={2} py={1} verticalAlign="top">
                <Link as={RouterLink} to={to} color="brand.500">
                  {item.name}
                </Link>
              </Td>
              <Td px={0} py={1} color="gray.500" verticalAlign="top" whiteSpace="nowrap">
                {due}
              </Td>
            </Tr>
          );
        })}
      </Tbody>
    </Table>
  );
}

function SectionBody({ section }) {
  switch (section.type) {
    case 'custom_message':
      return <TextContent content={section.content} />;
    case 'task_query':
      return <ItemsTable content={section.content} emptyLabel="No matching tasks." isTask />;
    case 'item_query':
      return (
        <>
          <ItemsTable content={section.content} emptyLabel="No matching items." isTask={false} />
          <CategoryTotals totals={section.content?.category_totals} />
        </>
      );
    default:
      return (
        <Text as="pre" fontSize="xs" color="gray.500" overflowX="auto">
          {JSON.stringify(section.content, null, 2)}
        </Text>
      );
  }
}

export default function MessageSections({ sections = [] }) {
  if (sections.length === 0) {
    return (
      <Text color="gray.500" fontSize="sm">
        (Empty report)
      </Text>
    );
  }
  return (
    <>
      {sections.map((section, i) => (
        <Box key={i} mt={i === 0 ? 0 : 3}>
          {section.heading && (
            <Heading size="xs" textTransform="uppercase" color="gray.400" mb={1}>
              {section.heading}
            </Heading>
          )}
          <SectionBody section={section} />
        </Box>
      ))}
    </>
  );
}
