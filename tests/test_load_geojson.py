"""
Tests for generic GeoJSON to BigQuery loader functionality.
Testing ONLY new code, not existing functionality.
"""

import pytest
import json
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point, Polygon, MultiPolygon
from google.cloud import bigquery
from unittest.mock import Mock, patch, MagicMock
import tempfile
import os

# Import the functions we're going to implement
from data.geospatial_data import load_geojson_to_bigquery
from data.bigquery_client import (
    insert_geodataframe_to_table,
    infer_bigquery_schema_from_geodataframe,
    create_table_with_schema
)


class TestGeoJSONSchemaInference:
    """Test dynamic schema inference from various GeoJSON structures."""
    
    def test_infer_schema_simple_point_features(self):
        """Test schema inference with simple Point features and flat properties."""
        # Create a simple GeoDataFrame
        gdf = gpd.GeoDataFrame(
            {
                'name': ['Location A', 'Location B'],
                'population': [1000, 2000],
                'temperature': [25.5, 30.2],
                'is_urban': [True, False]
            },
            geometry=[Point(-122.4, 37.8), Point(-122.5, 37.9)]
        )
        
        schema = infer_bigquery_schema_from_geodataframe(gdf)
        
        # Verify schema fields
        assert len(schema) == 5  # 4 properties + 1 geometry
        
        # Check field types
        field_dict = {field.name: field for field in schema}
        assert field_dict['name'].field_type == 'STRING'
        assert field_dict['population'].field_type == 'INTEGER'
        assert field_dict['temperature'].field_type == 'FLOAT'
        assert field_dict['is_urban'].field_type == 'BOOLEAN'
        assert field_dict['geometry'].field_type == 'GEOGRAPHY'
    
    def test_infer_schema_complex_nested_properties(self):
        """Test schema inference with nested properties (should be flattened)."""
        # Create GeoDataFrame with nested data
        gdf = gpd.GeoDataFrame(
            {
                'id': [1, 2],
                'properties.address.street': ['123 Main St', '456 Oak Ave'],
                'properties.address.city': ['San Francisco', 'Oakland'],
                'properties.metrics.value': [100.5, 200.7],
                'properties.tags': [['tag1', 'tag2'], ['tag3']]
            },
            geometry=[Point(-122.4, 37.8), Point(-122.5, 37.9)]
        )
        
        schema = infer_bigquery_schema_from_geodataframe(gdf)
        
        field_dict = {field.name: field for field in schema}
        # Nested objects should be flattened with dot notation
        assert 'properties.address.street' in field_dict
        assert 'properties.address.city' in field_dict
        assert 'properties.metrics.value' in field_dict
        # Arrays should be REPEATED fields
        assert field_dict['properties.tags'].mode == 'REPEATED'
    
    def test_infer_schema_mixed_geometry_types(self):
        """Test schema inference with different geometry types."""
        # Create GeoDataFrame with mixed geometries
        poly1 = Polygon([(-122, 37), (-122, 38), (-121, 38), (-121, 37)])
        poly2 = Polygon([(-123, 37), (-123, 38), (-122, 38), (-122, 37)])
        multi = MultiPolygon([poly1, poly2])
        
        gdf = gpd.GeoDataFrame(
            {'feature_id': [1, 2, 3]},
            geometry=[Point(-122.4, 37.8), poly1, multi]
        )
        
        schema = infer_bigquery_schema_from_geodataframe(gdf)
        
        # All geometry types should map to GEOGRAPHY
        field_dict = {field.name: field for field in schema}
        assert field_dict['geometry'].field_type == 'GEOGRAPHY'
    
    def test_infer_schema_with_null_values(self):
        """Test schema inference handles null values correctly."""
        gdf = gpd.GeoDataFrame(
            {
                'id': [1, 2, 3],
                'optional_field': ['value', None, 'another'],
                'numeric_field': [1.5, None, 3.0]
            },
            geometry=[Point(0, 0), Point(1, 1), Point(2, 2)]
        )
        
        schema = infer_bigquery_schema_from_geodataframe(gdf)
        
        # Fields with nulls should be NULLABLE (default)
        field_dict = {field.name: field for field in schema}
        assert field_dict['optional_field'].mode == 'NULLABLE'
        assert field_dict['numeric_field'].mode == 'NULLABLE'


class TestGeoJSONToBigQueryLoader:
    """Test the main GeoJSON to BigQuery loading functionality."""
    
    @patch('data.geospatial_data.gpd.read_file')
    @patch('data.bigquery_client.create_table_with_schema')
    @patch('data.bigquery_client.insert_geodataframe_to_table')
    def test_load_simple_geojson(self, mock_insert, mock_create, mock_read):
        """Test loading a simple GeoJSON file."""
        # Mock GeoDataFrame
        mock_gdf = gpd.GeoDataFrame(
            {'id': [1, 2], 'name': ['A', 'B']},
            geometry=[Point(0, 0), Point(1, 1)]
        )
        mock_read.return_value = mock_gdf
        
        # Test the load function
        load_geojson_to_bigquery(
            'test.geojson',
            'test_dataset',
            'test_table'
        )
        
        # Verify calls
        mock_read.assert_called_once_with('test.geojson')
        mock_create.assert_called_once()
        mock_insert.assert_called_once()
    
    @patch('data.geospatial_data.gpd.read_file')
    def test_load_geojson_with_crs_transformation(self, mock_read):
        """Test that non-WGS84 CRS is transformed."""
        # Create GeoDataFrame with different CRS
        mock_gdf = gpd.GeoDataFrame(
            {'id': [1]},
            geometry=[Point(500000, 4000000)],
            crs='EPSG:32633'  # UTM Zone 33N
        )
        mock_read.return_value = mock_gdf
        
        with patch('data.bigquery_client.insert_geodataframe_to_table') as mock_insert:
            load_geojson_to_bigquery('test.geojson', 'dataset', 'table')
            
            # Check that the GeoDataFrame was transformed to WGS84
            inserted_gdf = mock_insert.call_args[0][0]
            assert inserted_gdf.crs == 'EPSG:4326'
    
    def test_load_invalid_geojson_file(self):
        """Test error handling for invalid GeoJSON files."""
        with pytest.raises(Exception):
            load_geojson_to_bigquery(
                'nonexistent.geojson',
                'dataset',
                'table'
            )


class TestBigQueryOperations:
    """Test BigQuery-specific operations."""
    
    @patch('data.bigquery_client.initialize_bigquery_client')
    def test_create_table_with_geography_schema(self, mock_client):
        """Test creating a BigQuery table with GEOGRAPHY column."""
        mock_bq_client = Mock()
        mock_client.return_value = mock_bq_client
        
        schema = [
            bigquery.SchemaField('id', 'INTEGER'),
            bigquery.SchemaField('name', 'STRING'),
            bigquery.SchemaField('geometry', 'GEOGRAPHY')
        ]
        
        create_table_with_schema('test_dataset', 'test_table', schema)
        
        # Verify table creation was called
        mock_bq_client.create_table.assert_called_once()
        created_table = mock_bq_client.create_table.call_args[0][0]
        assert created_table.schema == schema
    
    @patch('data.bigquery_client.initialize_bigquery_client')
    def test_batch_insert_geodataframe(self, mock_client):
        """Test batch insertion of GeoDataFrame."""
        mock_bq_client = Mock()
        mock_client.return_value = mock_bq_client
        
        # Create test GeoDataFrame
        gdf = gpd.GeoDataFrame(
            {'id': range(150), 'value': range(150)},
            geometry=[Point(i, i) for i in range(150)]
        )
        
        insert_geodataframe_to_table(
            gdf,
            'test_dataset',
            'test_table',
            batch_size=50
        )
        
        # Should have been called 3 times (150 rows / 50 batch size)
        assert mock_bq_client.insert_rows_json.call_count == 3
    
    def test_geometry_to_wkt_conversion(self):
        """Test that geometries are converted to WKT for BigQuery."""
        from data.bigquery_client import _prepare_geodataframe_for_bigquery
        
        gdf = gpd.GeoDataFrame(
            {'id': [1, 2]},
            geometry=[
                Point(-122.4, 37.8),
                Polygon([(-122, 37), (-122, 38), (-121, 38), (-121, 37)])
            ]
        )
        
        prepared_data = _prepare_geodataframe_for_bigquery(gdf)
        
        # Geometry should be converted to WKT strings
        assert prepared_data[0]['geometry'] == 'POINT (-122.4 37.8)'
        assert prepared_data[1]['geometry'].startswith('POLYGON')


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_empty_geojson_file(self):
        """Test handling of empty GeoJSON file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.geojson', delete=False) as f:
            json.dump({"type": "FeatureCollection", "features": []}, f)
            temp_path = f.name
        
        try:
            with pytest.raises(ValueError, match="empty"):
                load_geojson_to_bigquery(temp_path, 'dataset', 'table')
        finally:
            os.unlink(temp_path)
    
    def test_geojson_without_properties(self):
        """Test GeoJSON features with no properties (geometry only)."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.geojson', delete=False) as f:
            geojson_data = {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "geometry": {"type": "Point", "coordinates": [-122.4, 37.8]},
                        "properties": {}
                    }
                ]
            }
            json.dump(geojson_data, f)
            temp_path = f.name
        
        try:
            # Should still work with geometry-only features
            with patch('data.bigquery_client.insert_geodataframe_to_table'):
                load_geojson_to_bigquery(temp_path, 'dataset', 'table')
        finally:
            os.unlink(temp_path)
    
    @patch('data.bigquery_client.initialize_bigquery_client')
    def test_bigquery_connection_error(self, mock_client):
        """Test handling of BigQuery connection errors."""
        mock_client.return_value = None  # Simulate connection failure
        
        with pytest.raises(Exception, match="BigQuery client"):
            create_table_with_schema('dataset', 'table', [])