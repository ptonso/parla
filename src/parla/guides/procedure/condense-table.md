---
kind: procedure
procedure: condense-table
---
Goal: fit a table to its budget while keeping what the argument compares.

You choose the content, and `parla tool table` formats it. Cut in this order and stop when the table fits: first the columns the project does not argue from (run ids, seeds, timestamps, counts a rate already implies); then cluster columns that describe one quantity, as `mean ± std` or an interval, by joining the existing strings; then shorten column names to the shortest unambiguous form; and last rows, keeping the proposed method, its baselines and any row the project singles out. Copy every value exactly, with its sign, unit and precision, and invent nothing. Keep the original row and column order and the identifying first column. Make the smallest cut that fits, write the result as a new source file, leave the original, and record what you removed and why.
