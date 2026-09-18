/**
 * MessageSections — renders a message's rendered section snapshots.
 *
 * A message stores an ordered list of sections, each a snapshot taken when the
 * report ran: `{ type, heading, content }`. This component knows how to display
 * each v1 section type (custom_message, task_query, item_query). Unknown types
 * fall back to a JSON dump so nothing is silently dropped.
 */

import { Box, Checkbox, Heading, Link, Table, Tbody, Td, Text, Tr, Wrap, WrapItem } from '@chakra-ui/react';
import { Link as RouterLink } from 'react-router-dom';

import { formatDate } from '../utils/dates';
import { resolveTaskRow } from '../utils/reportTasks';

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
 *
 * When `interactive` (task sections only, on the single-report page), the
 * leading emoji cell is replaced with a checkbox that completes/uncompletes the
 * real task. Row state (checked, emoji, due) is driven by the live task via
 * `taskState`; `onToggleTask(row)` is called on change and `togglingId` disables
 * the in-flight row. A task missing from `taskState` (deleted since the report
 * ran) shows a disabled checkbox reflecting the snapshot.
 */
function ItemsTable({ content, emptyLabel, isTask, interactive, taskState, onToggleTask, togglingId }) {
  const items = content?.items || [];
  if (items.length === 0) {
    return (
      <Text color="gray.500" fontSize="sm">
        {emptyLabel}
      </Text>
    );
  }
  const isInteractive = Boolean(interactive && isTask);
  return (
    <Table size="sm" variant="unstyled">
      <Tbody>
        {items.map((item) => {
          const id = isTask ? item.task_id : item.item_id;
          const to = isTask ? `/tasks/${id}` : `/items/${id}`;
          // For interactive task rows, live task state wins over the snapshot.
          const row = isInteractive ? resolveTaskRow(item, taskState) : null;
          const status = isTask ? (row ? row.computed_status : item.computed_status) : null;
          const done = row ? row.done : Boolean(isTask && item.done);
          const emoji = isTask ? STATUS_EMOJI[status] || DEFAULT_BULLET : DEFAULT_BULLET;
          const dueValue = isTask ? (row ? row.current_due : item.current_due) : item.use_by_date;
          const due = formatDate(dueValue);
          return (
            <Tr key={id} fontSize="sm">
              <Td px={0} py={1} width="1.75em" verticalAlign="top">
                {isInteractive ? (
                  <Checkbox
                    isChecked={done}
                    isDisabled={!row.exists || togglingId === id}
                    onChange={() => onToggleTask?.(row)}
                    colorScheme="brand"
                    mt={0.5}
                    aria-label={done ? `Mark ${row.name} not done` : `Mark ${row.name} done`}
                  />
                ) : (
                  emoji
                )}
              </Td>
              <Td px={2} py={1} verticalAlign="top">
                <Link
                  as={RouterLink}
                  to={to}
                  color="brand.500"
                  textDecoration={done ? 'line-through' : 'none'}
                >
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

function SectionBody({ section, interactive, taskState, onToggleTask, togglingId }) {
  switch (section.type) {
    case 'custom_message':
      return <TextContent content={section.content} />;
    case 'task_query':
      return (
        <ItemsTable
          content={section.content}
          emptyLabel="No matching tasks."
          isTask
          interactive={interactive}
          taskState={taskState}
          onToggleTask={onToggleTask}
          togglingId={togglingId}
        />
      );
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

/**
 * @param {object[]} sections - rendered section snapshots
 * @param {boolean} [interactive] - render task rows as completion checkboxes
 * @param {Map<string, object>} [taskState] - live tasks by id (interactive mode)
 * @param {(row: object) => void} [onToggleTask] - called when a task checkbox toggles
 * @param {string|null} [togglingId] - task_id currently mutating (disables its checkbox)
 */
export default function MessageSections({
  sections = [],
  interactive = false,
  taskState,
  onToggleTask,
  togglingId,
}) {
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
          <SectionBody
            section={section}
            interactive={interactive}
            taskState={taskState}
            onToggleTask={onToggleTask}
            togglingId={togglingId}
          />
        </Box>
      ))}
    </>
  );
}
