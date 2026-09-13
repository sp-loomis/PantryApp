/**
 * MessageSections — renders a message's rendered section snapshots.
 *
 * A message stores an ordered list of sections, each a snapshot taken when the
 * report ran: `{ type, heading, content }`. This component knows how to display
 * each v1 section type (custom_message, task_query, item_query). Unknown types
 * fall back to a JSON dump so nothing is silently dropped.
 */

import { Box, Heading, List, ListItem, Text } from '@chakra-ui/react';

function TextContent({ content }) {
  return <Text whiteSpace="pre-wrap">{content?.text || ''}</Text>;
}

function ItemsContent({ content, emptyLabel }) {
  const items = content?.items || [];
  if (items.length === 0) {
    return (
      <Text color="gray.500" fontSize="sm">
        {emptyLabel}
      </Text>
    );
  }
  return (
    <List spacing={1}>
      {items.map((item) => (
        <ListItem key={item.task_id || item.item_id} fontSize="sm">
          • {item.name}
        </ListItem>
      ))}
    </List>
  );
}

function SectionBody({ section }) {
  switch (section.type) {
    case 'custom_message':
      return <TextContent content={section.content} />;
    case 'task_query':
      return <ItemsContent content={section.content} emptyLabel="No matching tasks." />;
    case 'item_query':
      return <ItemsContent content={section.content} emptyLabel="No matching items." />;
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
