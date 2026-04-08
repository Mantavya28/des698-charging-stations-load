import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, Polygon, MultiPoint, box
from shapely.ops import voronoi_diagram
import json
import os
from pathlib import Path
import numpy as np
import streamlit as st

# Helper function for path resolution
def get_data_path(filename):
    """Get absolute path to data file, compatible with Streamlit Cloud."""
    base_dir = Path(__file__).parent
    return str(base_dir / filename)

# Global cache for the boundary to avoid reloading/reprojecting every time
CACHED_BOUNDARY = None
CACHED_POIS = None

@st.cache_resource
def load_and_process_pois(poi_file='delhi_pois.geojson'):
    """
    Loads POIs, projects them, and classifies them into demand categories.
    Returns a GeoDataFrame with a 'category' column.
    """
    global CACHED_POIS
    if CACHED_POIS is not None:
        return CACHED_POIS

    poi_path = get_data_path(poi_file)
    if not os.path.exists(poi_path):
        print(f"POI file not found: {poi_path}")
        return None

    try:
        # Load POIs
        gdf = gpd.read_file(poi_path)
        
        # Project to UTM 43N (Meters)
        gdf = gdf.to_crs("EPSG:32643")
        
        # Classification Logic
        # Categories: Shopping, Hospital, Restaurant, Office, Education, Residential
        
        def classify(row):
            # Safe get for properties
            amenity = row.get('amenity', '')
            shop = row.get('shop', '')
            office = row.get('office', '')
            landuse = row.get('landuse', '')
            healthcare = row.get('healthcare', '')
            
            # 1. Shopping (0.784)
            if shop or amenity in ['marketplace', 'mall']:
                return 'Shopping'
            
            # 2. Hospitals (0.780)
            if amenity in ['hospital', 'clinic'] or healthcare:
                return 'Hospital'
            
            # 3. Restaurants (0.743)
            if amenity in ['restaurant', 'fast_food', 'cafe', 'food_court']:
                return 'Restaurant'
            
            # 4. Offices (0.661)
            if office or amenity in ['office', 'bank']:
                return 'Office'
                
            # 5. Education (0.641)
            if amenity in ['university', 'college', 'school', 'kindergarten']:
                return 'Education'
                
            # 6. Residential (0.562)
            if landuse == 'residential':
                return 'Residential'
                
            return None

        gdf['category'] = gdf.apply(classify, axis=1)
        
        # Filter out unclassified
        gdf_classified = gdf.dropna(subset=['category'])
        
        # Cache
        CACHED_POIS = gdf_classified
        return gdf_classified
        
    except Exception as e:
        print(f"Error loading POIs: {e}")
        return None

def generate_voronoi_polygons(stations, boundary_file='delhi_boundary.geojson'):
    """
    Generates Voronoi polygons for the given stations, clipped to the Delhi boundary.
    Also calculates Demand Index based on POI density.
    """
    try:
        boundary_path = get_data_path(boundary_file)
        if not os.path.exists(boundary_path):
            print(f"Boundary file not found: {boundary_path}")
            return None
            
        global CACHED_BOUNDARY
        
        # 1. Load & Process Delhi Boundary (ONCE, PERSISTENT PRECISION)
        if CACHED_BOUNDARY is None:
            # Load
            delhi_gdf = gpd.read_file(boundary_path)
            
            # Project to UTM Zone 43N
            target_crs = "EPSG:32643"
            delhi_projected = delhi_gdf.to_crs(target_crs)
            
            # NOTE: Simplification REMOVED to restore precision as per user request.
            # delhi_projected['geometry'] = delhi_projected.simplify(100, preserve_topology=True)
            
            # valid geometry fix (self-intersection)
            delhi_projected['geometry'] = delhi_projected.geometry.buffer(0)
            
            CACHED_BOUNDARY = delhi_projected
        
        # Use cached version
        delhi_projected = CACHED_BOUNDARY
        target_crs = "EPSG:32643"
        
        # 2. Convert Stations to GeoDataFrame
        station_data = []
        for s in stations:
            station_data.append({
                'id': s['id'],
                'name': s['name'],
                'geometry': Point(s['lon'], s['lat']) 
            })
            
        stations_gdf = gpd.GeoDataFrame(station_data, crs="EPSG:4326")
        
        # 3. Project stations to same CRS
        stations_projected = stations_gdf.to_crs(target_crs)
        
        # 4. Generate Voronoi Polygons
        boundary_shape = delhi_projected.unary_union
        envelope = boundary_shape.envelope.buffer(20000)
        
        points_multi = MultiPoint(stations_projected.geometry.tolist())
        voronoi_regions = voronoi_diagram(points_multi, envelope=envelope)
        
        # 5. Assign Polygons back to Stations
        voronoi_polys = []
        for poly in voronoi_regions.geoms:
            voronoi_polys.append(poly)
            
        voronoi_gdf = gpd.GeoDataFrame(geometry=voronoi_polys, crs=target_crs)
        
        # Spatial join to match station ID to polygon
        # Spatial join to match station ID to polygon
        # 'inner' join ensures we only keep polygons that contain a station
        station_to_poly = gpd.sjoin(voronoi_gdf, stations_projected, how="inner", predicate="contains")
        
        # FIX: Drop 'index_right' to prevent collision in subsequent joins
        if 'index_right' in station_to_poly.columns:
            station_to_poly = station_to_poly.drop(columns=['index_right'])
        
        # 6. Clip to Delhi Boundary (High Precision Overlay)
        final_polygons = gpd.overlay(station_to_poly, delhi_projected, how='intersection')
        
        # 7. Spatial Join with POIs to Calculate Demand Index
        # ---------------------------------------------------------------------
        pois_gdf = load_and_process_pois()
        
        if pois_gdf is not None and not pois_gdf.empty:
            # Join: POI points -> Polygons
            final_polygons['poly_id'] = final_polygons.index
            joined = gpd.sjoin(pois_gdf, final_polygons, how='inner', predicate='within')
            
            # Calculate Area (Square km)
            final_polygons['area_km2'] = final_polygons.geometry.area / 1_000_000
            
            # Count POIs per Category per Polygon
            counts = joined.groupby(['poly_id', 'category']).size().unstack(fill_value=0)
            
            # Merge counts
            final_polygons = final_polygons.join(counts)
            
            # Fill missing
            cols = ['Shopping', 'Hospital', 'Restaurant', 'Office', 'Education', 'Residential']
            for c in cols:
                if c not in final_polygons:
                    final_polygons[c] = 0
                else:
                    final_polygons[c] = final_polygons[c].fillna(0)
            
            # Calculate Density & Weighted Index
            # Weights: Shop=0.784, Hosp=0.780, Rest=0.743, Off=0.661, Edu=0.641, Res=0.562
            
            final_polygons['demand_index'] = (
                0.784 * (final_polygons['Shopping'] / final_polygons['area_km2']) +
                0.780 * (final_polygons['Hospital'] / final_polygons['area_km2']) +
                0.743 * (final_polygons['Restaurant'] / final_polygons['area_km2']) +
                0.661 * (final_polygons['Office'] / final_polygons['area_km2']) +
                0.641 * (final_polygons['Education'] / final_polygons['area_km2']) +
                0.562 * (final_polygons['Residential'] / final_polygons['area_km2'])
            )
            
            # Map Index back to Station Objects
            index_map = final_polygons.set_index('id')['demand_index'].to_dict()
            for s in stations:
                sid = s['id']
                if sid in index_map:
                    s['demand_index'] = float(index_map[sid])
                else:
                    s['demand_index'] = 0.0

        else:
             # Fallback if POIs fail
            final_polygons['demand_index'] = 0.0
            for s in stations:
                s['demand_index'] = 0.0
        
        # 8. Reproject back to WGS84 (EPSG:4326)
        final_polygons_wgs84 = final_polygons.to_crs("EPSG:4326")
        
        return json.loads(final_polygons_wgs84.to_json())

    except Exception as e:
        error_msg = f"Error generating polygons: {str(e)}"
        print(error_msg)
        with open("voronoi_debug.log", "w") as f:
            f.write(error_msg)
            import traceback
            f.write("\n" + traceback.format_exc())
            
        return None
        return None

def redistribute_scenario_demand(base_stations, new_station_payload=None, disabled_ids=None):
    """
    Generates Voronoi for base +/- stations.
    Redistributes demand among affected stations based on Area and POI weights.
    Conserves total demand of the affected system.
    """
    if disabled_ids is None: disabled_ids = []
    
    try:
        # 1. Generate Baseline (Old) Polygons
        old_geojson = generate_voronoi_polygons(base_stations)
        if not old_geojson: return None
        
        old_features = {f['properties']['id']: f for f in old_geojson['features']}
        old_areas = {f['properties']['id']: f['properties'].get('area_km2', 0) for f in old_geojson['features']}
        old_demand = {f['properties']['id']: f['properties'].get('demand_index', 0) for f in old_geojson['features']}
        
        # 2. Prepare New Station List
        # Start with base, filter out disabled, append new
        new_stations = [s.copy() for s in base_stations if s['id'] not in disabled_ids]
        
        if new_station_payload:
            new_stations.append(new_station_payload)
        
        # 3. Generate Scenario (New) Polygons
        new_geojson = generate_voronoi_polygons(new_stations)
        if not new_geojson: return None
        
        new_features = {f['properties']['id']: f for f in new_geojson['features']}
        
        # 4. Identify Affected Stations
        affected_ids = []
        
        # The new station is inherently affected/involved if it exists
        if new_station_payload:
            new_id = new_station_payload['id']
            affected_ids.append(new_id)
        else:
            new_id = None
        
        # Survivors check for area change
        for sid, feat in new_features.items():
            if sid == new_id: continue
            
            # Check if area changed significantly (> 1%)
            old_area = old_areas.get(sid, 0)
            new_area = feat['properties'].get('area_km2', 0)
            
            if abs(new_area - old_area) > 0.01: # 0.01 sq km tolerance
                affected_ids.append(sid)
        
        # 5. Calculate Conservation Target (Total Demand of Affected Stations BEFORE change)
        total_demand_target = 0.0
        
        # Add demand from survivors
        for sid in affected_ids:
            if sid == new_id: continue # New station didn't exist, contributed 0
            total_demand_target += old_demand.get(sid, 0)
            
        # Add demand from DISABLED stations (closest approximation: their demand must go somewhere)
        # We assume the disabled stations' demand is absorbed by the affected neighbors
        for dis_id in disabled_ids:
             total_demand_target += old_demand.get(dis_id, 0)
            
        # 6. Calculate Raw Scores for Affected Stations (Area + POI)
        # Weights: alpha=0.5 (Area), beta=0.5 (POI)
        
        affected_stats = {}
        total_area_affected = 0.0
        total_poi_score_affected = 0.0
        
        for sid in affected_ids:
            feat = new_features[sid]
            area = feat['properties'].get('area_km2', 0)
            
            # Recalculate Raw POI Density Score (Sum of weights)
            # We need the absolute POI score, not the density index
            # Reverse engineer from demand_index? No, better to use the counts if available
            # Or just use the new demand index * area? 
            # The current 'demand_index' in new_features is already calculated by generate_voronoi using density
            # Let's use the 'demand_index' (Density) * 'area' as a proxy for "Total POI Value"
            
            poi_value = feat['properties'].get('demand_index', 0) * area
            
            affected_stats[sid] = {
                'area': area,
                'poi_value': poi_value
            }
            
            total_area_affected += area
            total_poi_score_affected += poi_value
            
        # 7. Compute Composite Weights and Redistribute
        redistributed_demand = {}
        impact_summary = {'total_redistributed': total_demand_target, 'details': []}
        
        # Safety check for divide by zero
        if total_area_affected == 0: total_area_affected = 1.0
        if total_poi_score_affected == 0: total_poi_score_affected = 1.0
        
        sum_normalized_weights = 0.0
        temp_weights = {}

        for sid in affected_ids:
            s_data = affected_stats[sid]
            
            norm_area = s_data['area'] / total_area_affected
            norm_poi = s_data['poi_value'] / total_poi_score_affected
            
            # Composite Weight (Alpha=0.5, Beta=0.5)
            raw_weight = (0.5 * norm_area) + (0.5 * norm_poi)
            temp_weights[sid] = raw_weight
            sum_normalized_weights += raw_weight
            
        # Final Normalization to match Target
        for sid in affected_ids:
            w = temp_weights[sid]
            # Normalize so weights sum to 1, then multiply by Target Total
            final_demand = (w / sum_normalized_weights) * total_demand_target
            
            redistributed_demand[sid] = final_demand
            
            # Record delta
            old_val = old_demand.get(sid, 0)
            delta = final_demand - old_val
            impact_summary['details'].append({
                'id': sid,
                'name': new_features[sid]['properties'].get('name', 'Unknown'),
                'old': old_val,
                'new': final_demand,
                'delta': delta
            })

            # Update Feature Property
            new_features[sid]['properties']['demand_index'] = final_demand
            
        # 8. Update GeoJSON features
        updated_features = []
        for sid, feat in new_features.items():
            # If not affected, it keeps its generated index (which should be same as old)
            # If affected, we overwrote it above
            updated_features.append(feat)
            
        return {
            "type": "FeatureCollection",
            "features": updated_features,
            "impact": impact_summary
        }

    except Exception as e:
        error_msg = f"Error in redistribution: {str(e)}"
        print(error_msg)
        with open("redist_debug.log", "w") as f:
            f.write(error_msg)
            import traceback
            f.write("\n" + traceback.format_exc())
        return None

def find_optimal_station_location(existing_stations, boundary_file='delhi_boundary.geojson', grid_resolution=0.02):
    """
    Finds the optimal location for a new battery swapping station by minimizing
    the standard deviation of demand indices across all stations.
    
    Args:
        existing_stations: List of existing station dictionaries
        boundary_file: Path to Delhi boundary GeoJSON file
        grid_resolution: Grid spacing in degrees (default 0.02 ≈ 2.2km)
    
    Returns:
        Dictionary with optimal location and statistics:
        {
            'lat': float,
            'lon': float,
            'std_dev': float,
            'demand_indices': dict,
            'all_stations': list
        }
    """
    try:
        # Load Delhi boundary
        boundary_path = get_data_path(boundary_file)
        if not os.path.exists(boundary_path):
            print(f"Boundary file not found: {boundary_path}")
            return None
        
        delhi_gdf = gpd.read_file(boundary_path)
        delhi_boundary = delhi_gdf.unary_union
        
        # Get boundary bounds
        minx, miny, maxx, maxy = delhi_boundary.bounds
        
        # Generate candidate grid points
        candidate_points = []
        lat_range = np.arange(miny, maxy, grid_resolution)
        lon_range = np.arange(minx, maxx, grid_resolution)
        
        for lat in lat_range:
            for lon in lon_range:
                point = Point(lon, lat)
                if delhi_boundary.contains(point):
                    candidate_points.append((lat, lon))
        
        print(f"Evaluating {len(candidate_points)} candidate locations...")
        
        # Evaluate each candidate
        best_location = None
        best_std_dev = float('inf')
        best_demand_indices = None
        best_all_stations = None
        
        for idx, (lat, lon) in enumerate(candidate_points):
            # Create temporary new station
            new_station = {
                'id': 'ST_NEW',
                'name': 'Candidate Station',
                'lat': lat,
                'lon': lon,
                'chargers': 20,
                'bays': 3,
                'inventory_cap': 20,
                'arrival_rate': 5.0,
                'service_rate': 0.5,
                'status': 'healthy',
                'is_new': True
            }
            
            # Combine with existing stations
            all_stations = existing_stations + [new_station]
            
            # Generate Voronoi polygons
            geojson = generate_voronoi_polygons(all_stations)
            
            if geojson and 'features' in geojson:
                # Extract demand indices
                demand_indices = {}
                for feature in geojson['features']:
                    station_id = feature['properties']['id']
                    demand_idx = feature['properties'].get('demand_index', 0)
                    demand_indices[station_id] = demand_idx
                
                # Calculate standard deviation
                if demand_indices:
                    values = list(demand_indices.values())
                    std_dev = np.std(values)
                    
                    # Update best if this is better
                    if std_dev < best_std_dev:
                        best_std_dev = std_dev
                        best_location = (lat, lon)
                        best_demand_indices = demand_indices.copy()
                        best_all_stations = all_stations.copy()
            
            # Progress indicator
            if (idx + 1) % 100 == 0:
                print(f"Evaluated {idx + 1}/{len(candidate_points)} locations...")
        
        if best_location:
            print(f"Optimal location found: {best_location} with std_dev={best_std_dev:.4f}")
            return {
                'lat': best_location[0],
                'lon': best_location[1],
                'std_dev': best_std_dev,
                'demand_indices': best_demand_indices,
                'all_stations': best_all_stations
            }
        else:
            print("No valid location found")
            return None
            
    except Exception as e:
        error_msg = f"Error in optimization: {str(e)}"
        print(error_msg)
        import traceback
        traceback.print_exc()
        return None
