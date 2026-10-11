/**
 * CategorySummaryCards
 *
 * A row of stat tiles at the top of the search results — one tile per category
 * present in the current (filtered) results, showing that category's total
 * measure. Totals come from the `/search` response (`category_totals`), so they
 * reflect whatever filters are active. Renders nothing when no categorized
 * items match.
 */

import { Card, CardBody, Stat, StatLabel, StatNumber, Wrap, WrapItem } from '@chakra-ui/react';
import { formatTotal } from '@pantry-app/shared';

export default function CategorySummaryCards({ totals }) {
  if (!totals || totals.length === 0) return null;

  return (
    <Wrap spacing={3} mb={4}>
      {totals.map((t) => (
        <WrapItem key={t.category_id}>
          <Card variant="outline" minW="140px">
            <CardBody py={3}>
              <Stat>
                <StatLabel color="gray.600" noOfLines={1}>{t.name}</StatLabel>
                <StatNumber fontSize="2xl">
                  {formatTotal(t.value)}{' '}
                  <StatNumber as="span" fontSize="md" fontWeight="normal" color="gray.600">
                    {t.unit}
                  </StatNumber>
                </StatNumber>
              </Stat>
            </CardBody>
          </Card>
        </WrapItem>
      ))}
    </Wrap>
  );
}
