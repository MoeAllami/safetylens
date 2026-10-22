-- First characters of one complaint's narrative, for showing a search hit in the terminal.
SELECT left(regexp_replace(coalesce(narrative, ''), '\s+', ' ', 'g'), $chars)
FROM complaint_docs
WHERE odino = $odino
