/**
 * Icons
 *
 * Single indirection point for the app's icons. Each export wraps a react-icons
 * icon in Chakra's <Icon as=.../> so it accepts boxSize/color/margin props.
 *
 * To swap an icon: browse react-icons.github.io, import the icon you want (any
 * pack, e.g. `fi`, `md`, `hi2`, `fa6`, `lu`), and change the `as` here — callers
 * are untouched. Current set is Feather (`fi`) to match the original look.
 */

import { Icon } from '@chakra-ui/react';
import {
  FiChevronRight,
  FiArrowLeft,
  FiEdit2,
  FiTrash2,
  FiClock,
  FiBell,
  FiPlay,
  FiSettings,
  FiSlack,
} from 'react-icons/fi';
import {
  RiSearch2Line,
  RiFridgeLine,
  RiPriceTag3Line,
  RiAddCircleLine,
  RiCalendarTodoLine,
  RiMegaphoneLine,
} from 'react-icons/ri';

export const SearchIcon = (props) => <Icon as={RiSearch2Line} {...props} />;
export const LocationIcon = (props) => <Icon as={RiFridgeLine} {...props} />;
export const TagIcon = (props) => <Icon as={RiPriceTag3Line} {...props} />;
export const PlusIcon = (props) => <Icon as={RiAddCircleLine} {...props} />;
export const TaskIcon = (props) => <Icon as={RiCalendarTodoLine} {...props} />;
export const ChevronRightIcon = (props) => <Icon as={FiChevronRight} {...props} />;
export const BackIcon = (props) => <Icon as={FiArrowLeft} {...props} />;
export const EditIcon = (props) => <Icon as={FiEdit2} {...props} />;
export const TrashIcon = (props) => <Icon as={FiTrash2} {...props} />;
export const ClockIcon = (props) => <Icon as={FiClock} {...props} />;
export const BellIcon = (props) => <Icon as={FiBell} {...props} />;
export const RunIcon = (props) => <Icon as={FiPlay} {...props} />;
export const ReportIcon = (props) => <Icon as={RiMegaphoneLine} {...props} />;
export const SettingsIcon = (props) => <Icon as={FiSettings} {...props} />;
export const SlackIcon = (props) => <Icon as={FiSlack} {...props} />;
