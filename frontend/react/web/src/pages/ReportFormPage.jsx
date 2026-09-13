/**
 * ReportFormPage — create or edit a scheduled report.
 *
 * One component for both modes (keyed on the :reportId param). Controlled state
 * drives a schedule sub-form and an ordered section-rule builder. Section config
 * fields are type-specific (custom message text, task/item query filters).
 */

import { useCallback, useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  Box,
  Button,
  Center,
  Checkbox,
  Divider,
  Flex,
  FormControl,
  FormLabel,
  Heading,
  HStack,
  IconButton,
  Input,
  Select,
  Spinner,
  Text,
  Textarea,
  VStack,
} from '@chakra-ui/react';
import { Select as MultiSelect } from 'chakra-react-select';
import {
  getReport,
  createReport,
  updateReport,
  listTags,
  validateReportName,
  validateSchedule,
} from '@pantry-app/shared';
import PageHeader from '../components/PageHeader';
import ErrorMessage from '../components/ErrorMessage';
import LocationSelect from '../components/LocationSelect';
import { PlusIcon, TrashIcon } from '../components/icons';

const WEEKDAYS = [
  { value: 0, label: 'Monday' },
  { value: 1, label: 'Tuesday' },
  { value: 2, label: 'Wednesday' },
  { value: 3, label: 'Thursday' },
  { value: 4, label: 'Friday' },
  { value: 5, label: 'Saturday' },
  { value: 6, label: 'Sunday' },
];

// Reports fire on the hour (the notification sweep runs hourly), so the time
// picker offers whole-hour options only: "00:00" .. "23:00".
const HOURS = Array.from({ length: 24 }, (_, h) => `${String(h).padStart(2, '0')}:00`);

const SECTION_TYPES = [
  { value: 'custom_message', label: 'Custom message' },
  { value: 'task_query', label: 'Task query' },
  { value: 'item_query', label: 'Item / inventory query' },
];

function browserTz() {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
  } catch {
    return 'UTC';
  }
}

function defaultSection(type) {
  return { type, heading: '', config: {} };
}

/** A name (partial match) text field, shared by the query section types. */
function NameFilter({ config, set }) {
  return (
    <FormControl>
      <FormLabel fontSize="sm">Name contains (optional)</FormLabel>
      <Input
        value={config.name || ''}
        onChange={(e) => set('name', e.target.value || undefined)}
        placeholder="Partial name match, e.g. milk"
      />
    </FormControl>
  );
}

/** A tag multiselect, fed by the user's existing tags. */
function TagsFilter({ config, set, tagOptions }) {
  const selected = (config.tags || []).map((t) => ({ value: t, label: t }));
  return (
    <FormControl>
      <FormLabel fontSize="sm">Tags (optional)</FormLabel>
      <MultiSelect
        isMulti
        options={tagOptions}
        value={selected}
        onChange={(opts) => set('tags', opts && opts.length ? opts.map((o) => o.value) : undefined)}
        placeholder="Any tag"
        size="md"
      />
    </FormControl>
  );
}

/** Type-specific config editor for one section. */
function SectionConfig({ section, onConfigChange, tagOptions }) {
  const { type, config } = section;
  const set = (key, value) => onConfigChange({ ...config, [key]: value });

  if (type === 'custom_message') {
    return (
      <FormControl>
        <FormLabel fontSize="sm">Message text</FormLabel>
        <Textarea
          value={config.text || ''}
          onChange={(e) => set('text', e.target.value)}
          placeholder="Anything you want included in the report."
          rows={2}
        />
      </FormControl>
    );
  }
  if (type === 'task_query') {
    return (
      <VStack align="stretch" spacing={3}>
        <FormControl>
          <FormLabel fontSize="sm">Status</FormLabel>
          <Select
            value={config.status || 'active'}
            onChange={(e) => set('status', e.target.value)}
          >
            <option value="active">Active (incomplete)</option>
            <option value="done">Done</option>
            <option value="all">All</option>
          </Select>
        </FormControl>
        <TagsFilter config={config} set={set} tagOptions={tagOptions} />
        <NameFilter config={config} set={set} />
      </VStack>
    );
  }
  // item_query
  return (
    <VStack align="stretch" spacing={3}>
      <FormControl>
        <FormLabel fontSize="sm">Location (optional)</FormLabel>
        <LocationSelect
          value={config.location_id || ''}
          onChange={(e) => set('location_id', e.target.value || undefined)}
          placeholder="All locations"
        />
      </FormControl>
      <TagsFilter config={config} set={set} tagOptions={tagOptions} />
      <NameFilter config={config} set={set} />
    </VStack>
  );
}

export default function ReportFormPage() {
  const { reportId } = useParams();
  const isEdit = Boolean(reportId);
  const navigate = useNavigate();

  const [name, setName] = useState('');
  const [enabled, setEnabled] = useState(true);
  const [frequency, setFrequency] = useState('daily');
  const [timeOfDay, setTimeOfDay] = useState('09:00');
  const [weekday, setWeekday] = useState(0);
  const [dayOfMonth, setDayOfMonth] = useState(1);
  const [tz] = useState(browserTz());
  const [sections, setSections] = useState([defaultSection('task_query')]);

  const [fieldErrors, setFieldErrors] = useState({});
  const [loading, setLoading] = useState(isEdit);
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [tagOptions, setTagOptions] = useState([]);

  // Load the user's tag list once for the tag multiselects.
  useEffect(() => {
    listTags()
      .then((all) => setTagOptions(all.map((t) => ({ value: t, label: t }))))
      .catch(() => setTagOptions([]));
  }, []);

  const loadExisting = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const report = await getReport(reportId);
      const s = report.schedule || {};
      setName(report.name);
      setEnabled(report.enabled ?? true);
      setFrequency(s.frequency || 'daily');
      // Legacy schedules may carry a non-zero minute; floor to the hour so the
      // whole-hour picker has a matching option.
      setTimeOfDay(`${(s.time_of_day || '09:00').slice(0, 2)}:00`);
      setWeekday(s.weekday ?? 0);
      setDayOfMonth(s.day_of_month ?? 1);
      setSections(
        (report.sections || []).map((sec) => {
          const config = { ...(sec.config || {}) };
          // Migrate a legacy scalar tag to the tags array the control expects.
          if (config.tag && !config.tags) {
            config.tags = [config.tag];
            delete config.tag;
          }
          return { type: sec.type, heading: sec.heading || '', config };
        }),
      );
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, [reportId]);

  useEffect(() => {
    if (isEdit) loadExisting();
  }, [isEdit, loadExisting]);

  const buildSchedule = () => {
    const schedule = { frequency, time_of_day: timeOfDay, tz };
    if (frequency === 'weekly') schedule.weekday = Number(weekday);
    if (frequency === 'monthly') schedule.day_of_month = Number(dayOfMonth);
    return schedule;
  };

  const updateSection = (index, patch) => {
    setSections((prev) => prev.map((sec, i) => (i === index ? { ...sec, ...patch } : sec)));
  };

  const changeSectionType = (index, type) => {
    // Reset config when the type changes so stale keys don't leak through.
    updateSection(index, { type, config: {} });
  };

  const addSection = () => setSections((prev) => [...prev, defaultSection('custom_message')]);
  const removeSection = (index) =>
    setSections((prev) => prev.filter((_, i) => i !== index));

  const validate = () => {
    const errors = {};
    const nameErr = validateReportName(name);
    if (nameErr) errors.name = nameErr;
    const schedErr = validateSchedule(buildSchedule());
    if (schedErr) errors.schedule = schedErr;
    if (sections.length === 0) errors.sections = 'Add at least one section';
    sections.forEach((sec, i) => {
      if (sec.type === 'custom_message' && !(sec.config.text || '').trim()) {
        errors[`section_${i}`] = 'Custom message needs some text';
      }
    });
    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!validate()) return;

    const payload = {
      name: name.trim(),
      enabled,
      schedule: buildSchedule(),
      sections,
    };

    try {
      setSubmitting(true);
      setError(null);
      const saved = isEdit
        ? await updateReport(reportId, payload)
        : await createReport(payload);
      navigate('/reports');
      return saved;
    } catch (err) {
      setError(err);
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <Center py={12}>
        <Spinner color="brand.500" thickness="3px" />
      </Center>
    );
  }

  return (
    <Box>
      <PageHeader title={isEdit ? 'Edit report' : 'New report'} back />
      <ErrorMessage error={error} />

      <form onSubmit={handleSubmit}>
        <VStack spacing={5} align="stretch" maxW="560px">
          <FormControl isInvalid={!!fieldErrors.name} isRequired>
            <FormLabel>Name</FormLabel>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Daily chore digest"
              autoFocus
            />
            {fieldErrors.name && (
              <Text color="red.500" fontSize="sm" mt={1}>
                {fieldErrors.name}
              </Text>
            )}
          </FormControl>

          {/* Schedule sub-form */}
          <Box>
            <Heading size="sm" mb={3}>
              Schedule
            </Heading>
            <HStack align="start" spacing={3}>
              <FormControl>
                <FormLabel fontSize="sm">Frequency</FormLabel>
                <Select value={frequency} onChange={(e) => setFrequency(e.target.value)}>
                  <option value="daily">Daily</option>
                  <option value="weekly">Weekly</option>
                  <option value="monthly">Monthly</option>
                </Select>
              </FormControl>
              <FormControl>
                <FormLabel fontSize="sm">Time</FormLabel>
                <Select value={timeOfDay} onChange={(e) => setTimeOfDay(e.target.value)}>
                  {HOURS.map((h) => (
                    <option key={h} value={h}>
                      {h}
                    </option>
                  ))}
                </Select>
              </FormControl>
              {frequency === 'weekly' && (
                <FormControl>
                  <FormLabel fontSize="sm">Day</FormLabel>
                  <Select value={weekday} onChange={(e) => setWeekday(Number(e.target.value))}>
                    {WEEKDAYS.map((d) => (
                      <option key={d.value} value={d.value}>
                        {d.label}
                      </option>
                    ))}
                  </Select>
                </FormControl>
              )}
              {frequency === 'monthly' && (
                <FormControl>
                  <FormLabel fontSize="sm">Day of month</FormLabel>
                  <Input
                    type="number"
                    min={1}
                    max={28}
                    value={dayOfMonth}
                    onChange={(e) => setDayOfMonth(Number(e.target.value))}
                  />
                </FormControl>
              )}
            </HStack>
            <Text fontSize="xs" color="gray.400" mt={1}>
              Times are in your timezone ({tz}).
            </Text>
            {fieldErrors.schedule && (
              <Text color="red.500" fontSize="sm" mt={1}>
                {fieldErrors.schedule}
              </Text>
            )}
          </Box>

          <FormControl>
            <Checkbox
              isChecked={enabled}
              onChange={(e) => setEnabled(e.target.checked)}
              colorScheme="brand"
            >
              Enabled (runs on schedule)
            </Checkbox>
          </FormControl>

          <Divider />

          {/* Section builder */}
          <Box>
            <Flex align="center" justify="space-between" mb={3}>
              <Heading size="sm">Sections</Heading>
              <Button size="sm" leftIcon={<PlusIcon boxSize={4} />} onClick={addSection}>
                Add section
              </Button>
            </Flex>
            {fieldErrors.sections && (
              <Text color="red.500" fontSize="sm" mb={2}>
                {fieldErrors.sections}
              </Text>
            )}
            <VStack spacing={3} align="stretch">
              {sections.map((section, index) => (
                <Box
                  key={index}
                  borderWidth="1px"
                  borderColor="gray.200"
                  borderRadius="lg"
                  p={3}
                  bg="white"
                >
                  <Flex align="center" justify="space-between" mb={2} gap={2}>
                    <FormControl maxW="220px">
                      <Select
                        size="sm"
                        value={section.type}
                        onChange={(e) => changeSectionType(index, e.target.value)}
                      >
                        {SECTION_TYPES.map((t) => (
                          <option key={t.value} value={t.value}>
                            {t.label}
                          </option>
                        ))}
                      </Select>
                    </FormControl>
                    <IconButton
                      aria-label="Remove section"
                      icon={<TrashIcon />}
                      size="sm"
                      variant="ghost"
                      colorScheme="red"
                      onClick={() => removeSection(index)}
                    />
                  </Flex>
                  <FormControl mb={2}>
                    <FormLabel fontSize="sm">Heading (optional)</FormLabel>
                    <Input
                      size="sm"
                      value={section.heading}
                      onChange={(e) => updateSection(index, { heading: e.target.value })}
                      placeholder="Section heading"
                    />
                  </FormControl>
                  <SectionConfig
                    section={section}
                    onConfigChange={(config) => updateSection(index, { config })}
                    tagOptions={tagOptions}
                  />
                  {fieldErrors[`section_${index}`] && (
                    <Text color="red.500" fontSize="sm" mt={1}>
                      {fieldErrors[`section_${index}`]}
                    </Text>
                  )}
                </Box>
              ))}
            </VStack>
          </Box>

          <Button type="submit" isLoading={submitting} loadingText="Saving..." width="full">
            {isEdit ? 'Save changes' : 'Create report'}
          </Button>
        </VStack>
      </form>
    </Box>
  );
}
