# Execution Plan: Generic GeoJSON to BigQuery Loader

## Design Principle: Software-Defined Interface
Create a general-purpose GeoJSON loader that works with ANY valid GeoJSON structure, not tailored to specific files in `data/local/`.

### Interface Requirements
- Must handle all valid GeoJSON types (Point, LineString, Polygon, MultiPoint, MultiLineString, MultiPolygon, GeometryCollection)
- Must dynamically infer schema from ANY GeoJSON properties
- Must handle arbitrary nesting levels in properties
- Must not hardcode assumptions about specific property names or structures
- Must follow the GeoJSON RFC 7946 specification

## ⚠️ CRITICAL: Code Discovery Required First

This plan requires code discovery first. Before implementation, we MUST:
1. Search for existing GeoJSON to BigQuery implementations
2. Read at least 5 relevant files
3. Use minimum 3 different search patterns
4. Review existing functionality before creating new code

## Phase 1: Code Discovery (REQUIRED FIRST)

### Search Requirements
- [ ] Search patterns to execute:
  - `grep -r "geojson.*bigquery\|bigquery.*geojson"`
  - `grep -r "insert.*bigquery\|load.*bigquery"`
  - `grep -r "schema.*infer\|infer.*schema"`
  - `glob **/*load*.py`
  - `glob **/*geojson*.py`
- [ ] Files to read (minimum 5):
  - `data/bigquery_client.py` - Existing BigQuery operations
  - `data/geospatial_data.py` - Current GeoJSON handling
  - `config/settings.py` - Configuration patterns
  - Any files found containing "load", "insert", or "schema"
  - Check imports in data processing modules

### Expected Findings
- How does `data/geospatial_data.py` currently load GeoJSON?
- What BigQuery operations exist in `data/bigquery_client.py`?
- Are there existing batch insert functions?
- Is there schema inference code?
- What patterns exist for data loading?

## Phase 2: TDD Implementation (After Code Discovery)

### PRAGMATIC APPROACH: Test New Code Only
We will apply TDD only to the new functionality we're implementing, not to existing code.

### RED Phase - Write Failing Tests First
**⏸️ PAUSE POINT: Wait for approval after writing tests**

Location: `tests/test_load_geojson.py` (only for new functions)

Test scenarios for NEW generic functionality:
1. Test with various GeoJSON structures (not just our example files):
   - Simple Point features with flat properties
   - Complex MultiPolygon with nested properties
   - Features with arrays and mixed types
   - GeoJSON with no properties (geometry only)
   - FeatureCollection vs single Feature
2. Test dynamic schema inference:
   - Detecting property types correctly
   - Handling nested objects → flattened columns
   - Arrays → REPEATED fields in BigQuery
   - Null values and optional fields
3. Test geometry handling:
   - All GeoJSON geometry types
   - Conversion to BigQuery GEOGRAPHY type
4. Test error handling:
   - Invalid GeoJSON structure
   - Unsupported property types
   - BigQuery schema conflicts

**Skip testing**: Existing functions in `data/geospatial_data.py` or `data/bigquery_client.py`

### GREEN Phase - Minimal Implementation
**⏸️ PAUSE POINT: Wait for review after minimal code**

Based on code discovery, either:
- **EXTEND** existing functions (test only the new methods/logic)
- **REUSE** existing code without modification (no tests needed)
- **CREATE** new functionality (full TDD required)

### REFACTOR Phase - Improve Code
- Run tests for new code only
- Improve new code quality without changing behavior
- Re-run tests for new code

## Phase 3: Implementation Plan (Pending Discovery)

### Option A: Extend Existing Code (Preferred)
If discovery finds similar functionality:
1. Add GENERIC methods to `data/geospatial_data.py`:
   ```python
   def load_geojson_to_bigquery(
       file_path: str,
       dataset_id: str, 
       table_id: str,
       schema_config: Optional[Dict] = None
   ) -> None:
       """
       Generic loader for ANY valid GeoJSON file.
       No assumptions about property names or structure.
       """
   ```
2. Extend `data/bigquery_client.py` with generic insert:
   ```python
   def insert_geodataframe_dynamic(
       gdf: gpd.GeoDataFrame,
       dataset_id: str,
       table_id: str,
       infer_schema: bool = True
   ) -> None:
       """
       Dynamically infer schema from GeoDataFrame.
       Handle any property structure without hardcoding.
       """
   ```

### Option B: Create New Generic Interface (Only if Necessary)
If no suitable code exists after thorough search:
1. Create `scripts/load_geojson.py` with:
   - Dynamic schema inference engine
   - Property type detection (including nested objects/arrays)
   - Geometry type handling for all GeoJSON types
   - No hardcoded field names or structures
2. Design for extensibility:
   - Plugin system for custom transformations
   - Schema override capabilities
   - Configurable type mappings

### Makefile Creation
```makefile
# Only create after confirming no existing automation
.PHONY: help setup download-gcs-data load-geojson test-load clean

help:
	@echo "Available commands:"
	@echo "  setup            - Install dependencies and configure environment"
	@echo "  download-gcs-data - Download data files from Google Cloud Storage"
	@echo "  load-geojson     - Load GeoJSON file to BigQuery"
	@echo "  test-load        - Dry run validation of GeoJSON loading"
	@echo "  clean            - Clean up temporary files"

setup:
	python -m venv venv
	. venv/bin/activate && pip install -r requirements.txt

download-gcs-data:
	@echo "Running existing GCS downloader script..."
	python download_gcs_data.py

load-geojson:
	@if [ -z "$(FILE)" ]; then \
		echo "Error: FILE parameter is required"; \
		echo "Usage: make load-geojson FILE=path/to/file.geojson"; \
		exit 1; \
	fi
	python scripts/load_geojson.py --file $(FILE) $(ARGS)

test-load:
	@if [ -z "$(FILE)" ]; then \
		echo "Error: FILE parameter is required"; \
		echo "Usage: make test-load FILE=path/to/file.geojson"; \
		exit 1; \
	fi
	python scripts/load_geojson.py --file $(FILE) --dry-run

clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	rm -rf .pytest_cache
```

## Phase 4: Obsolete Code Handling

If new code replaces existing functionality:
1. Comment out old code with:
   ```python
   # OBSOLETE: [Date] - Replaced by load_geojson_to_bigquery()
   ```
2. Keep commented code for reference
3. Notify author of all obsoleted sections

## Decision Tree

```
Need GeoJSON to BigQuery loader?
├─ YES → Search existing code (Phase 1)
│   ├─ Found similar? → Extend/Reuse (Option A)
│   ├─ Found partial? → Extend with new methods
│   └─ Nothing found? → TDD new implementation (Option B)
└─ NO → Stop
```

## Conflict Resolution

| Situation | Action |
|-----------|--------|
| Found GeoJSON loader without BigQuery | Extend with BigQuery functionality |
| Found BigQuery insert without GeoJSON | Extend with GeoJSON parsing |
| Found both separately | Combine using existing patterns |
| Multiple implementations | Use best, mark others OBSOLETE |

## ⚠️ CRITICAL REMINDERS

1. **DO NOT PROCEED** without completing Phase 1 (Code Discovery)
2. **DO NOT CREATE** new files if existing code can be extended
3. **DO NOT SKIP** TDD pause points
4. **DO NOT DELETE** obsolete code - comment it out

## Success Criteria

- [ ] Completed thorough code search (3+ patterns, 5+ files)
- [ ] Written tests first (RED phase) for GENERIC functionality
- [ ] Tests cover diverse GeoJSON structures (not specific to our examples)
- [ ] Implementation handles ANY valid GeoJSON file
- [ ] No hardcoded assumptions about property names or structure
- [ ] Dynamic schema inference works with arbitrary nesting
- [ ] Received approval to proceed to GREEN phase
- [ ] Minimal implementation passes all tests
- [ ] Refactored code maintains all tests passing
- [ ] Documented any obsoleted code
- [ ] Updated CLAUDE.md with new functionality

## Generic Interface Design

The loader must implement a true software-defined interface:

```python
# Example interface (pending discovery phase)
class GeoJSONLoader:
    """Generic GeoJSON to BigQuery loader - works with ANY valid GeoJSON."""
    
    def infer_schema(self, geojson: Dict) -> List[bigquery.SchemaField]:
        """Dynamically infer BigQuery schema from GeoJSON structure."""
        
    def transform_features(self, features: List[Dict]) -> pd.DataFrame:
        """Transform GeoJSON features to BigQuery-compatible format."""
        
    def load(self, file_path: str, dataset_id: str, table_id: str) -> None:
        """Load any GeoJSON file to BigQuery without assumptions."""
```

This is NOT tailored to specific files like `power_lines_points_us.geojson` or `north_dakota_oil_wells.geojson`.