# HackSmart Digital Twin - Streamlit Cloud Deployment Guide

## Overview
This application is optimized for deployment on Streamlit Cloud with caching, error handling, and resource optimization.

## Deployment Steps

### 1. Prerequisites
- GitHub repository with your code
- Streamlit Cloud account (https://streamlit.io/cloud)

### 2. Required Files
Ensure these files are in your repository:
- ✅ `app.py` - Main application
- ✅ `requirements.txt` - Python dependencies
- ✅ `packages.txt` - System dependencies
- ✅ `.streamlit/config.toml` - Streamlit configuration
- ✅ All data files (CSV, Excel, GeoJSON)

### 3. Deploy to Streamlit Cloud

#### Option A: Via Streamlit Cloud Dashboard
1. Go to https://share.streamlit.io/
2. Sign in with GitHub
3. Click "New app"
4. Select your repository
5. Set main file path: `app.py`
6. Click "Deploy"

#### Option B: Via Button
Add this to your GitHub README:
```markdown
[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://share.streamlit.io)
```

### 4. Configuration

The app includes optimized settings in `.streamlit/config.toml`:
- Maximum upload size: 200MB
- Headless mode enabled
- Custom theme matching the app design
- Performance optimizations

### 5. Data Files Required

Ensure these files are in the repository root:
```
hacksmart_demo/
├── app.py
├── spatial_utils.py
├── battery_simulation.py
├── rebalancing.py
├── requirements.txt
├── packages.txt
├── .streamlit/
│   └── config.toml
├── delhi_boundary.geojson
├── delhi_pois.geojson
├── hacksmart_frontend.xlsx
├── full_dataset.csv
├── demand.csv
├── topology.csv
├── stations.csv
└── greenswap_logo.png
```

## Optimizations Applied

### 1. Caching Strategy
- `@st.cache_data` for data loading functions (TTL: 1 hour)
- `@st.cache_resource` for GeoDataFrame processing
- Reduces redundant computations and speeds up page loads

### 2. Error Handling
- Graceful degradation for missing files
- User-friendly error messages
- Fallback mechanisms for data loading

### 3. Memory Management
- Efficient session state usage
- Cached expensive operations
- Optimized simulation parameters

### 4. Cloud-Specific Optimizations
- System dependencies in `packages.txt`
- Version-pinned requirements
- Headless OpenCV for reduced memory footprint
- Proper configuration for cloud environment

## Performance Tips

### For Best Performance:
1. Keep data files under 100MB each
2. Use the app during off-peak hours initially
3. Monitor resource usage in Streamlit Cloud dashboard
4. Consider data compression for large GeoJSON files

### Monitoring
- Check Streamlit Cloud logs for any warnings
- Monitor memory usage in the dashboard
- Watch for timeout errors during heavy simulations

## Troubleshooting

### Common Issues

**Issue**: App crashes during initialization
- **Solution**: Check logs for missing data files
- Verify all required files are committed to GitHub

**Issue**: Slow loading times
- **Solution**: Already optimized with caching
- First load may be slow; subsequent loads will be faster

**Issue**: Geospatial operations fail
- **Solution**: `packages.txt` includes required GDAL libraries
- Verify packages.txt is in root directory

**Issue**: Memory limit exceeded
- **Solution**: Streamlit Cloud free tier has 1GB limit
- Consider upgrading to paid tier for more resources
- Or optimize simulation parameters to use less memory

## Resource Limits (Streamlit Cloud Free Tier)

- **Memory**: 1 GB RAM
- **CPU**: Shared
- **Storage**: Ephemeral (resets on redeploy)
- **Bandwidth**: Fair use policy

## Support

For issues related to:
- **Streamlit Cloud**: https://docs.streamlit.io/streamlit-community-cloud
- **App Issues**: Check the GitHub repository issues
- **General Streamlit**: https://discuss.streamlit.io/

## Environment Variables (Optional)

If you need to add secrets (API keys, etc.):
1. Go to App Settings in Streamlit Cloud
2. Navigate to "Secrets"
3. Add key-value pairs in TOML format

Example:
```toml
[database]
host = "your-host"
port = 5432
```

Access in code:
```python
import streamlit as st
host = st.secrets["database"]["host"]
```

## Updates and Redeployment

The app will automatically redeploy when you push to the main branch of your GitHub repository. Changes typically take 1-2 minutes to appear.

## Performance Metrics

Expected performance on Streamlit Cloud:
- **Initial Load**: 10-15 seconds (first user)
- **Cached Load**: 2-3 seconds (subsequent loads)
- **Simulation**: 5-10 seconds (7-day run)
- **Map Rendering**: 2-4 seconds

---

**Version**: 1.0  
**Last Updated**: 2026-02-01  
**Optimized for**: Streamlit Cloud
