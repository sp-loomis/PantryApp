/**
 * DecisionButtons — a compact Yes/No answer control for a decision task.
 *
 * Replaces the completion checkbox when a task's `answer_mode` is `yesno`. The
 * side matching the current answer (`decision`) is filled; clicking a side
 * answers that way (or, if already chosen, clears the answer). Mobile-friendly:
 * two thumb-sized buttons instead of a tiny checkbox.
 */

import { Button, ButtonGroup } from '@chakra-ui/react';

/**
 * @param {'yes'|'no'|null} [decision] - the current answer (null = unanswered)
 * @param {boolean} [isDisabled] - disable both buttons (e.g. in-flight / deleted)
 * @param {(decision: 'yes'|'no') => void} onAnswer - called with the clicked side
 * @param {string} [name] - task name, for accessible labels
 * @param {string} [size]
 */
export default function DecisionButtons({ decision, isDisabled, onAnswer, name = 'task', size = 'xs' }) {
  return (
    <ButtonGroup size={size} isAttached variant="outline">
      <Button
        colorScheme="green"
        variant={decision === 'yes' ? 'solid' : 'outline'}
        isDisabled={isDisabled}
        onClick={() => onAnswer?.('yes')}
        aria-label={`Answer yes to ${name}`}
        aria-pressed={decision === 'yes'}
      >
        Yes
      </Button>
      <Button
        colorScheme="red"
        variant={decision === 'no' ? 'solid' : 'outline'}
        isDisabled={isDisabled}
        onClick={() => onAnswer?.('no')}
        aria-label={`Answer no to ${name}`}
        aria-pressed={decision === 'no'}
      >
        No
      </Button>
    </ButtonGroup>
  );
}
