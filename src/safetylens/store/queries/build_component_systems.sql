-- Lookup from the full hierarchical component text to its top-level system,
-- e.g. 'SERVICE BRAKES, HYDRAULIC' -> 'SERVICE BRAKES', 'STRUCTURE:BODY' -> 'STRUCTURE'.
CREATE OR REPLACE TABLE component_systems AS
SELECT component, component_system FROM complaints WHERE component IS NOT NULL
UNION
SELECT component, component_system FROM recalls WHERE component IS NOT NULL
ORDER BY component
