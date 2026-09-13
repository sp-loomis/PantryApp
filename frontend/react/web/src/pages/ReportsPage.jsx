/**
 * ReportsPage — manage scheduled reports.
 *
 * Lists a user's report configs with their schedule summary and next run. Each
 * can be run now (generates a message immediately), edited, or deleted. Running
 * a report surfaces a toast linking to the generated message.
 */

import { useCallback, useEffect, useState } from 'react';
import { Link as RouterLink, useNavigate } from 'react-router-dom';
import {
  Badge,
  Box,
  Button,
  Center,
  Flex,
  Heading,
  HStack,
  IconButton,
  Spinner,
  Text,
  useToast,
  VStack,
} from '@chakra-ui/react';
import { listReports, runReport, deleteReport } from '@pantry-app/shared';
import EmptyState from '../components/EmptyState';
import ErrorMessage from '../components/ErrorMessage';
import { PlusIcon, EditIcon, TrashIcon, RunIcon } from '../components/icons';

const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

function scheduleSummary(schedule = {}) {
  const time = schedule.time_of_day || '09:00';
  switch (schedule.frequency) {
    case 'daily':
      return `Daily at ${time}`;
    case 'weekly':
      return `Weekly on ${WEEKDAYS[schedule.weekday ?? 0]} at ${time}`;
    case 'monthly':
      return `Monthly on day ${schedule.day_of_month ?? 1} at ${time}`;
    default:
      return 'No schedule';
  }
}

function formatWhen(iso) {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

export default function ReportsPage() {
  const toast = useToast();
  const navigate = useNavigate();
  const [reports, setReports] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [runningId, setRunningId] = useState(null);

  const load = useCallback(async () => {
    try {
      setError(null);
      setReports(await listReports());
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const handleRun = async (report) => {
    setRunningId(report.report_id);
    try {
      const message = await runReport(report.report_id);
      toast({
        title: `Generated “${report.name}”`,
        description: 'Open it in Messages.',
        status: 'success',
        duration: 5000,
        isClosable: true,
      });
      navigate(`/messages#${message.message_id}`);
    } catch (err) {
      setError(err);
    } finally {
      setRunningId(null);
    }
  };

  const handleDelete = async (report) => {
    try {
      await deleteReport(report.report_id);
      await load();
    } catch (err) {
      setError(err);
    }
  };

  return (
    <Box>
      <Flex align="center" justify="space-between" mb={4} gap={3}>
        <Text fontSize="2xl" fontWeight="bold">
          Reports
        </Text>
        <Button as={RouterLink} to="/reports/new" leftIcon={<PlusIcon boxSize={4} />}>
          New report
        </Button>
      </Flex>

      <ErrorMessage error={error} />

      {loading ? (
        <Center py={12}>
          <Spinner color="brand.500" thickness="3px" />
        </Center>
      ) : reports.length === 0 ? (
        <EmptyState
          title="No reports yet"
          description="Create a report to get scheduled summaries of your tasks and inventory."
          action={
            <Button as={RouterLink} to="/reports/new" mt={2}>
              New report
            </Button>
          }
        />
      ) : (
        <VStack spacing={3} align="stretch">
          {reports.map((report) => (
            <Box
              key={report.report_id}
              bg="white"
              borderWidth="1px"
              borderColor="gray.200"
              borderRadius="lg"
              boxShadow="sm"
              p={4}
            >
              <Flex align="center" justify="space-between" gap={3}>
                <Box minW={0}>
                  <HStack spacing={2}>
                    <Heading size="sm" noOfLines={1}>
                      {report.name}
                    </Heading>
                    {!report.enabled && <Badge colorScheme="gray">Paused</Badge>}
                  </HStack>
                  <Text fontSize="sm" color="gray.500">
                    {scheduleSummary(report.schedule)} · {report.sections?.length || 0} section
                    {report.sections?.length === 1 ? '' : 's'}
                  </Text>
                  <Text fontSize="xs" color="gray.400">
                    Next run: {formatWhen(report.next_run)}
                  </Text>
                </Box>
                <HStack spacing={1} flexShrink={0}>
                  <IconButton
                    aria-label="Run now"
                    icon={<RunIcon />}
                    size="sm"
                    variant="ghost"
                    colorScheme="brand"
                    isLoading={runningId === report.report_id}
                    onClick={() => handleRun(report)}
                  />
                  <IconButton
                    aria-label="Edit report"
                    icon={<EditIcon />}
                    size="sm"
                    variant="ghost"
                    as={RouterLink}
                    to={`/reports/${report.report_id}/edit`}
                  />
                  <IconButton
                    aria-label="Delete report"
                    icon={<TrashIcon />}
                    size="sm"
                    variant="ghost"
                    colorScheme="red"
                    onClick={() => handleDelete(report)}
                  />
                </HStack>
              </Flex>
            </Box>
          ))}
        </VStack>
      )}
    </Box>
  );
}
