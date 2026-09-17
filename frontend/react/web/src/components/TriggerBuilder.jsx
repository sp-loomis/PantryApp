/**
 * TriggerBuilder — edits a report's optional category-condition trigger.
 *
 * A trigger gates report generation: on schedule, the report is generated only
 * when the trigger passes against live data. It is a two-level boolean:
 *   - a list of CONDITIONS joined by an outer all/any, each with
 *   - a query (which items to look at) + a list of INEQUALITIES on category
 *     aggregates, joined by an inner all/any.
 *
 * Shape (see reportService.js / backend report_conditions.py):
 *   { match, conditions: [{ query: {location_id, tags, name}, match,
 *                           inequalities: [{category_id, operator, threshold}] }] }
 *
 * With no conditions the report always generates on schedule.
 */

import { useEffect, useState } from 'react';
import {
  Box,
  Button,
  Flex,
  FormControl,
  FormLabel,
  Heading,
  HStack,
  IconButton,
  Input,
  Select,
  Text,
  VStack,
} from '@chakra-ui/react';
import { Select as MultiSelect } from 'chakra-react-select';
import { listCategories } from '@pantry-app/shared';
import LocationSelect from './LocationSelect';
import { PlusIcon, TrashIcon } from './icons';

const MATCH_OPTIONS = [
  { value: 'all', label: 'ALL of' },
  { value: 'any', label: 'ANY of' },
];

function emptyInequality(categoryId = '') {
  return { category_id: categoryId, operator: 'below', threshold: '' };
}

function emptyCondition() {
  return { query: {}, match: 'all', inequalities: [emptyInequality()] };
}

export default function TriggerBuilder({ value, onChange, tagOptions = [] }) {
  const [categories, setCategories] = useState([]);

  useEffect(() => {
    listCategories()
      .then(setCategories)
      .catch(() => setCategories([]));
  }, []);

  const trigger = value || { match: 'all', conditions: [] };
  const conditions = trigger.conditions || [];

  const setTrigger = (patch) => onChange({ ...trigger, ...patch });
  const setConditions = (next) => setTrigger({ conditions: next });

  const updateCondition = (i, patch) =>
    setConditions(conditions.map((c, idx) => (idx === i ? { ...c, ...patch } : c)));
  const addCondition = () => setConditions([...conditions, emptyCondition()]);
  const removeCondition = (i) => setConditions(conditions.filter((_, idx) => idx !== i));

  const updateInequality = (ci, ii, patch) => {
    const cond = conditions[ci];
    const next = cond.inequalities.map((q, idx) => (idx === ii ? { ...q, ...patch } : q));
    updateCondition(ci, { inequalities: next });
  };
  const addInequality = (ci) => {
    const cond = conditions[ci];
    updateCondition(ci, { inequalities: [...cond.inequalities, emptyInequality()] });
  };
  const removeInequality = (ci, ii) => {
    const cond = conditions[ci];
    updateCondition(ci, { inequalities: cond.inequalities.filter((_, idx) => idx !== ii) });
  };

  const unitFor = (categoryId) => {
    const cat = categories.find((c) => c.category_id === categoryId);
    if (!cat) return '';
    return cat.measure_type === 'count' ? 'items' : cat.preferred_unit || '';
  };

  return (
    <Box>
      <Flex align="center" justify="space-between" mb={1}>
        <Heading size="sm">Trigger (optional)</Heading>
        <Button size="sm" leftIcon={<PlusIcon boxSize={4} />} onClick={addCondition}>
          Add condition
        </Button>
      </Flex>
      <Text fontSize="xs" color="gray.400" mb={3}>
        Only generate this report when category totals meet a condition (e.g. beef below
        10 lb). Leave empty to always generate on schedule.
      </Text>

      {conditions.length === 0 ? (
        <Text fontSize="sm" color="gray.500">
          No condition — this report always generates on schedule.
        </Text>
      ) : (
        <VStack align="stretch" spacing={3}>
          {conditions.length > 1 && (
            <HStack>
              <Text fontSize="sm">Fire when</Text>
              <Select
                size="sm"
                maxW="120px"
                value={trigger.match || 'all'}
                onChange={(e) => setTrigger({ match: e.target.value })}
              >
                {MATCH_OPTIONS.map((m) => (
                  <option key={m.value} value={m.value}>
                    {m.label}
                  </option>
                ))}
              </Select>
              <Text fontSize="sm">these conditions hold:</Text>
            </HStack>
          )}

          {conditions.map((cond, ci) => (
            <Box key={ci} borderWidth="1px" borderColor="gray.200" borderRadius="lg" p={3} bg="white">
              <Flex align="center" justify="space-between" mb={2}>
                <Text fontSize="sm" fontWeight="semibold">
                  Condition {ci + 1}
                </Text>
                <IconButton
                  aria-label="Remove condition"
                  icon={<TrashIcon />}
                  size="sm"
                  variant="ghost"
                  colorScheme="red"
                  onClick={() => removeCondition(ci)}
                />
              </Flex>

              {/* Query: which items to aggregate over. */}
              <VStack align="stretch" spacing={2} mb={3}>
                <FormControl>
                  <FormLabel fontSize="sm">Items in location (optional)</FormLabel>
                  <LocationSelect
                    value={cond.query?.location_id || ''}
                    onChange={(e) =>
                      updateCondition(ci, {
                        query: { ...cond.query, location_id: e.target.value || undefined },
                      })
                    }
                    placeholder="All locations"
                  />
                </FormControl>
                <FormControl>
                  <FormLabel fontSize="sm">Tags (optional)</FormLabel>
                  <MultiSelect
                    isMulti
                    options={tagOptions}
                    value={(cond.query?.tags || []).map((t) => ({ value: t, label: t }))}
                    onChange={(opts) =>
                      updateCondition(ci, {
                        query: {
                          ...cond.query,
                          tags: opts && opts.length ? opts.map((o) => o.value) : undefined,
                        },
                      })
                    }
                    placeholder="Any tag"
                  />
                </FormControl>
                <FormControl>
                  <FormLabel fontSize="sm">Name contains (optional)</FormLabel>
                  <Input
                    value={cond.query?.name || ''}
                    onChange={(e) =>
                      updateCondition(ci, {
                        query: { ...cond.query, name: e.target.value || undefined },
                      })
                    }
                    placeholder="Partial name match"
                  />
                </FormControl>
              </VStack>

              {/* Inequalities on category aggregates. */}
              {cond.inequalities.length > 1 && (
                <HStack mb={2}>
                  <Text fontSize="sm">Match</Text>
                  <Select
                    size="sm"
                    maxW="110px"
                    value={cond.match || 'all'}
                    onChange={(e) => updateCondition(ci, { match: e.target.value })}
                  >
                    {MATCH_OPTIONS.map((m) => (
                      <option key={m.value} value={m.value}>
                        {m.label}
                      </option>
                    ))}
                  </Select>
                  <Text fontSize="sm">the checks below</Text>
                </HStack>
              )}

              <VStack align="stretch" spacing={2}>
                {cond.inequalities.map((ineq, ii) => (
                  <HStack key={ii} align="center">
                    <Select
                      size="sm"
                      flex="1"
                      placeholder="Category"
                      value={ineq.category_id}
                      onChange={(e) => updateInequality(ci, ii, { category_id: e.target.value })}
                    >
                      {categories.map((c) => (
                        <option key={c.category_id} value={c.category_id}>
                          {c.name}
                        </option>
                      ))}
                    </Select>
                    <Select
                      size="sm"
                      maxW="110px"
                      value={ineq.operator}
                      onChange={(e) => updateInequality(ci, ii, { operator: e.target.value })}
                    >
                      <option value="below">below</option>
                      <option value="above">above</option>
                    </Select>
                    <Input
                      size="sm"
                      type="number"
                      maxW="110px"
                      value={ineq.threshold}
                      onChange={(e) => updateInequality(ci, ii, { threshold: e.target.value })}
                      placeholder="amount"
                    />
                    <Text fontSize="sm" color="gray.500" minW="3em">
                      {unitFor(ineq.category_id)}
                    </Text>
                    <IconButton
                      aria-label="Remove check"
                      icon={<TrashIcon />}
                      size="sm"
                      variant="ghost"
                      colorScheme="red"
                      onClick={() => removeInequality(ci, ii)}
                      isDisabled={cond.inequalities.length === 1}
                    />
                  </HStack>
                ))}
                <Button
                  size="xs"
                  variant="ghost"
                  leftIcon={<PlusIcon boxSize={3} />}
                  onClick={() => addInequality(ci)}
                  alignSelf="flex-start"
                >
                  Add check
                </Button>
              </VStack>
            </Box>
          ))}
        </VStack>
      )}
    </Box>
  );
}
