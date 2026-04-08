import pandas as pd
from shapely.geometry import Point, Polygon, MultiPoint, box, shape
from shapely.ops import voronoi_diagram, unary_union
import json
import os
from pathlib import Path
import numpy as np
import streamlit as st
from pyproj import Transformer

# Helper function for path resolution
def get_data_path(filename):
    """Get absolute path to data file, compatible with Streamlit Cloud."""
    base_dir = Path(__file__).parent
    return str(base_dir / filename)

# Coordinate Tansformers
# EPSG:4326 (WGS84) to EPSG:32643 (UTM Zone 43N - Delhi)
TRANSFORMER_TO_UTM = Transformer.from_crs("EPSG:4326", "EPSG:32643", always_xy=True)
TRANSFORMER_TO_WGS = Transformer.from_crs("EPSG:32643", "EPSG:4326", always_xy=True)

def project_point(lon, lat):
    return TRANSFORMER_TO_UTM.transform(lon, lat)

def unproject_point(x, y):
    return TRANSFORMER_TO_WGS.transform(x, y)

def project_geometry(geom):
    """Recursively project shapely geometry to UTM 43N."""
    if geom.is_empty:
        return geom
    if isinstance(geom, Point):
        return Point(project_point(geom.x, geom.y))
    elif isinstance(geom, Polygon):
        shell = [project_point(x, y) for x, y in geom.exterior.coords]
        holes = []
        for hole in geom.interiors:
            holes.append([project_point(x, y) for x, y in hole.coords])
        return Polygon(shell, holes)
    elif isinstance(geom, MultiPoint):
        return MultiPoint([project_geometry(p) for p in geom.geoms])
    # Add other types if necessary, but Delhi boundary is usually Polygon/MultiPolygon
    elif hasattr(geom, "geoms"):
        return type(geom)([project_geometry(g) for g in geom.geoms])
    return geom

def unproject_geometry(geom):
    """Recursively unproject shapely geometry to WGS84."""
    if geom.is_empty:
        return geom
    if isinstance(geom, Point):
        return Point(unproject_point(geom.x, geom.y))
    elif isinstance(geom, Polygon):
        shell = [unproject_point(x, y) for x, y in geom.exterior.coords]
        holes = []
        for hole in geom.interiors:
            holes.append([unproject_point(x, y) for x, y in hole.coords])
        return Polygon(shell, holes)
    elif hasattr(geom, "geoms"):
        return type(geom)([unproject_geometry(g) for g in geom.geoms])
    return geom

# Global cache for the boundary to avoid reloading/reprojecting every time
CACHED_BOUNDARY = None
CACHED_POIS = None

@st.cache_resource
def load_and_process_pois(poi_file='delhi_pois.geojson'):
    """
    Loads POIs, projects them, and classifies them into demand categories.
    Returns a list of dictionaries with 'geometry' (UTM) and 'category'.
    """
    global CACHED_POIS
    if CACHED_POIS is not None:
        return CACHED_POIS

    poi_path = get_data_path(poi_file)
    if not os.path.exists(poi_path):
        print(f"POI file not found: {poi_path}")
        return []

    try:
        with open(poi_path, 'r') as f:
            data = json.load(f)
        
        processed_pois = []
        for feature in data['features']:
            props = feature.get('properties', {})
            geom = shape(feature['geometry'])
            
            # Classification Logic
            category = None
            amenity = props.get('amenity', '')
            shop = props.get('shop', '')
            office = props.get('office', '')
            landuse = props.get('landuse', '')
            healthcare = props.get('healthcare', '')
            
            if shop or amenity in ['marketplace', 'mall']:
                category = 'Shopping'
            elif amenity in ['hospital', 'clinic'] or healthcare:
                category = 'Hospital'
            elif amenity in ['restaurant', 'fast_food', 'cafe', 'food_court']:
                category = 'Restaurant'
            elif office or amenity in ['office', 'bank']:
                category = 'Office'
            elif amenity in ['university', 'college', 'school', 'kindergarten']:
                category = 'Education'
            elif landuse == 'residential':
                category = 'Residential'
            
            if category:
                # Project point to UTM
                point_utm = project_geometry(geom)
                processed_pois.append({
                    'geometry': point_utm,
                    'category': category
                })
        
        CACHED_POIS = processed_pois
        return processed_pois
        
    except Exception as e:
        print(f"Error loading POIs: {e}")
        return []

def generate_voronoi_polygons(stations, boundary_file='delhi_boundary.geojson'):
    """
    Generates Voronoi polygons for the given stations, clipped to the Delhi boundary.
    Replaced GeoPandas with native Shapely + PyProj for Vercel compatibility.
    """
    try:
        boundary_path = get_data_path(boundary_file)
        if not os.path.exists(boundary_path):
            print(f"Boundary file not found: {boundary_path}")
            return None
            
        global CACHED_BOUNDARY
        
        # 1. Load & Process Delhi Boundary
        if CACHED_BOUNDARY is None:
            with open(boundary_path, 'r') as f:
                b_data = json.load(f)
            
            # Merge all features into one boundary shape
            boundary_shapes = [shape(f['geometry']) for f in b_data['features']]
            merged_boundary = unary_union(boundary_shapes)
            
            # Project to UTM 43N
            CACHED_BOUNDARY = project_geometry(merged_boundary).buffer(0)
        
        delhi_utm = CACHED_BOUNDARY
        
        # 2. Project Stations to UTM
        stations_utm = []
        for s in stations:
            p_utm = project_point(s['lon'], s['lat'])
            stations_utm.append({
                'id': s['id'],
                'name': s['name'],
                'geom': Point(p_utm)
            })
            
        # 3. Generate Voronoi Polygons
        boundary_envelope = delhi_utm.envelope.buffer(20000)
        points_multi = MultiPoint([s['geom'] for s in stations_utm])
        voronoi_regions = voronoi_diagram(points_multi, envelope=boundary_envelope)
        
        # 4. Map Polygons to Stations & Clip
        # Voronoi regions are geometries, we need to find which station each belongs to
        final_features = []
        pois = load_and_process_pois()
        
        for poly in voronoi_regions.geoms:
            # Clip to Delhi boundary
            clipped_poly = poly.intersection(delhi_utm)
            if clipped_poly.is_empty:
                continue
                
            # Find station inside this poly
            matching_station = None
            for s in stations_utm:
                if poly.contains(s['geom']):
                    matching_station = s
                    break
            
            if not matching_station:
                continue
            
            # 5. POI Density Calculation (Native Sjoin)
            area_km2 = clipped_poly.area / 1_000_000
            poi_counts = {
                'Shopping': 0, 'Hospital': 0, 'Restaurant': 0, 
                'Office': 0, 'Education': 0, 'Residential': 0
            }
            
            for poi in pois:
                if clipped_poly.contains(poi['geometry']):
                    poi_counts[poi['category']] += 1
            
            # Weights: Shop=0.784, Hosp=0.780, Rest=0.743, Off=0.661, Edu=0.641, Res=0.562
            demand_index = (
                0.784 * (poi_counts['Shopping'] / area_km2) +
                0.780 * (poi_counts['Hospital'] / area_km2) +
                0.743 * (poi_counts['Restaurant'] / area_km2) +
                0.661 * (poi_counts['Office'] / area_km2) +
                0.641 * (poi_counts['Education'] / area_km2) +
                0.562 * (poi_counts['Residential'] / area_km2)
            ) if area_km2 > 0 else 0
            
            # Update station object directly as requested by legacy code
            for s in stations:
                if s['id'] == matching_station['id']:
                    s['demand_index'] = float(demand_index)
            
            # Prepare properties for GeoJSON
            props = {
                'id': matching_station['id'],
                'name': matching_station['name'],
                'area_km2': float(area_km2),
                'demand_index': float(demand_index),
                **poi_counts
            }
            
            # Reproject back to WGS84 for Folium
            poly_wgs = unproject_geometry(clipped_poly)
            
            final_features.append({
                "type": "Feature",
                "geometry": poly_wgs.__geo_interface__,
                "properties": props
            })
            
        return {
            "type": "FeatureCollection",
            "features": final_features
        }

    except Exception as e:
        error_msg = f"Error generating polygons: {str(e)}"
        print(error_msg)
        return None

def redistribute_scenario_demand(base_stations, new_station_payload=None, disabled_ids=None):
    """
    Native implementation of demand redistribution without GeoPandas.
    """
    if disabled_ids is None: disabled_ids = []
    
    try:
        # 1. Baseline
        old_geojson = generate_voronoi_polygons(base_stations)
        if not old_geojson: return None
        
        old_demand = {f['properties']['id']: f['properties'].get('demand_index', 0) for f in old_geojson['features']}
        old_areas = {f['properties']['id']: f['properties'].get('area_km2', 0) for f in old_geojson['features']}
        
        # 2. New Scenario
        new_stations = [s.copy() for s in base_stations if s['id'] not in disabled_ids]
        if new_station_payload:
            new_stations.append(new_station_payload)
            
        new_geojson = generate_voronoi_polygons(new_stations)
        if not new_geojson: return None
        
        new_features = {f['properties']['id']: f for f in new_geojson['features']}
        
        # 3. Sustainability Logic (Simplified Redistribution)
        affected_ids = []
        if new_station_payload:
            affected_ids.append(new_station_payload['id'])
            
        for sid, feat in new_features.items():
            if new_station_payload and sid == new_station_payload['id']: continue
            old_area = old_areas.get(sid, 0)
            new_area = feat['properties'].get('area_km2', 0)
            if abs(new_area - old_area) > 0.01:
                affected_ids.append(sid)
                
        total_demand_target = sum(old_demand.get(sid, 0) for sid in affected_ids if sid in old_demand)
        total_demand_target += sum(old_demand.get(dis_id, 0) for dis_id in disabled_ids)
        
        total_score = 0
        scores = {}
        for sid in affected_ids:
            feat = new_features[sid]
            # Score = Area * Density Proxy (composite of POIs)
            # Use demand_index (which is density) * area = total absolute score
            score = feat['properties'].get('demand_index', 0) * feat['properties'].get('area_km2', 0)
            scores[sid] = score
            total_score += score
            
        if total_score > 0:
            for sid in affected_ids:
                new_val = (scores[sid] / total_score) * total_demand_target
                new_features[sid]['properties']['demand_index'] = float(new_val)
        
        return new_geojson

    except Exception as e:
        print(f"Error in redistribution: {e}")
        return None

def find_optimal_station_location(existing_stations, boundary_file='delhi_boundary.geojson', grid_resolution=0.02):
    """
    Optimization search without GeoPandas.
    """
    try:
        boundary_path = get_data_path(boundary_file)
        with open(boundary_path, 'r') as f:
            b_data = json.load(f)
        boundary_shapes = [shape(f['geometry']) for f in b_data['features']]
        delhi_boundary = unary_union(boundary_shapes)
        
        minx, miny, maxx, maxy = delhi_boundary.bounds
        lat_range = np.arange(miny, maxy, grid_resolution)
        lon_range = np.arange(minx, maxx, grid_resolution)
        
        candidate_points = []
        for lat in lat_range:
            for lon in lon_range:
                if delhi_boundary.contains(Point(lon, lat)):
                    candidate_points.append((lat, lon))
        
        best_location = None
        best_std_dev = float('inf')
        
        # NOTE: Native Voronoi in loop is expensive, keeping limited candidates for speed if on Vercel
        max_evals = 50 
        eval_points = candidate_points[::max(1, len(candidate_points)//max_evals)]
        
        for lat, lon in eval_points:
            new_station = {
                'id': 'ST_NEW', 'name': 'Candidate', 'lat': lat, 'lon': lon,
                'arrival_rate': 5.0, 'chargers': 20, 'service_rate': 0.5, 'inventory_cap': 20
            }
            all_stations = existing_stations + [new_station]
            geojson = generate_voronoi_polygons(all_stations)
            
            if geojson:
                indices = [f['properties']['demand_index'] for f in geojson['features']]
                if indices:
                    std_dev = np.std(indices)
                    if std_dev < best_std_dev:
                        best_std_dev = std_dev
                        best_location = (lat, lon)
        
        if best_location:
            return {'lat': best_location[0], 'lon': best_location[1], 'std_dev': best_std_dev}
        return None
            
    except Exception as e:
        print(f"Error in optimization: {e}")
        return None
