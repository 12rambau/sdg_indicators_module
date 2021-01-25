from functools import partial

import ee 

from component import parameter as pm

ee.Initialize()

def integrate_ndvi_climate(aoi_io, io, output):
    
    # create the composite image collection
    i_img_coll = ee.ImageCollection([])
    
    for sensor in io.sensors:
        
        # get the image collection 
        # filter its bounds to fit the aoi extends 
        # rename the bands 
        # adapt the resolution to meet sentinel 2 native one (10m)
        # mask the clouds and adapt the scale 
        sat = ee.ImageCollection(pm.sensors[sensor]) \
            .filterBounds(aoi_io.get_aoi_ee()) \
            .map(partial(rename_band, sensor=sensor)) \
            .map(partial(adapt_res, sensor=sensor)) \
            .map(partial(cloud_mask, sensor=sensor)) 
    
        i_img_coll = i_img_coll.merge(sat)
    
    # Filtering the img collection  using start year and end year
    i_img_coll = i_img_coll.filterDate(f'{io.start}-01-01', f'{io.end}-12-31')

    # Function to integrate observed NDVI datasets at the annual level
    ndvi_coll = i_img_coll.map(CalcNDVI)
    
    ndvi_int = int_yearly_ndvi(ndvi_coll, io.start, io.end)

    # process the climate dataset to use with the pixel restrend, RUE calculation
    precipitation = ee.ImageCollection(pm.precipitation) \
        .filterBounds(aoi_io.get_aoi_ee()) \
        .filterDate(f'{io.start}-01-01',f'{io.end}-12-31') \
        .select('precipitation')
    
    climate_int = int_yearly_climate(precipitation, io.start, io.end)
    
    return (ndvi_int, climate_int)

def rename_band(img, sensor):
    
    if sensor in ['Landsat 4', 'Landsat 5', 'Landsat 7']:
        img = img.select(['B3', 'B4', 'pixel_qa'],['Red', 'NIR',  'pixel_qa'])
    elif sensor == 'Landsat 8':
        img = img.select(['B4', 'B5', 'pixel_qa'],['Red', 'NIR', 'pixel_qa']) 
    elif sensor == 'Sentinel 2':
        img = img.select(['B8', 'B4', 'QA60'],['Red', 'NIR', 'QA60'])
        
    return img

def adapt_res(img, sensor):
    """reproject landasat images in the sentinel resolution"""
    
    # get sentinel projection
    sentinel_proj = ee.ImageCollection('COPERNICUS/S2').first().projection()
    
    # change landsat resolution 
    if sensor in ['landsat 8, Landsat 7, Landsat 5, Landsat 4']:
        img = img.changeProj(img.projection(), sentinel_proj)
        
    # the reflectance alignment won't be a problem as we don't use the bands per se but only the computed ndvi
        
    return img

def cloud_mask(img, sensor):
    """ mask the clouds based on the sensor name, sentine 2 data will be multiplyed by 10000 to meet the scale of landsat data"""

    if sensor in ['Landsat 5', 'Landsat 7', 'Landsat 4']:
        qa = img.select('pixel_qa')
        # If the cloud bit (5) is set and the cloud confidence (7) is high
        # or the cloud shadow bit is set (3), then it's a bad pixel.
        cloud = qa.bitwiseAnd(1 << 5).And(qa.bitwiseAnd(1 << 7)).Or(qa.bitwiseAnd(1 << 3))
        # Remove edge pixels that don't occur in all bands
        mask2 = img.mask().reduce(ee.Reducer.min())
            
        img =  img.updateMask(cloud.Not()).updateMask(mask2)
        
    elif sensor == 'Landsat 8':
        # Bits 3 and 5 are cloud shadow and cloud, respectively.
        cloudShadowBitMask = (1 << 3)
        cloudsBitMask = (1 << 5)
        # Get the pixel QA band.
        qa = img.select('pixel_qa')
        # Both flags should be set to zero, indicating clear conditions.
        mask = qa.bitwiseAnd(cloudShadowBitMask).eq(0).And(qa.bitwiseAnd(cloudsBitMask).eq(0))
            
        img = img.updateMask(mask)
        
    elif sensor == 'Sentinel 2':
        qa = img.select('QA60')
        # Bits 10 and 11 are clouds and cirrus, respectively.
        cloudBitMask = (1 << 10)
        cirrusBitMask = (1 << 11)
        # Both flags should be set to zero, indicating clear conditions.
        mask = qa.bitwiseAnd(cloudBitMask).eq(0).And(qa.bitwiseAnd(cirrusBitMask).eq(0))
    
        img = img.updateMask(mask)#.divide(10000)
        
    return img 

def int_yearly_ndvi(ndvi_coll, start, end):
    """Function to integrate observed NDVI datasets at the annual level"""
    
    img_coll = ee.List([])
    for year in range(start, end + 1):
        # get the ndvi img
        ndvi_img = ndvi_coll \
            .filterDate(f'{year}-01-01', f'{year}-12-31') \
            .reduce(ee.Reducer.mean()) \
            .rename('ndvi')
        
        # convert to float
        con_img = ee.Image(year).float().rename('year')
        img = ndvi_img.addBands(con_img).set({'year': year})
        
        # append to the collection
        img_coll = img_coll.add(img)
        
    return ee.ImageCollection(img_coll)

def int_yearly_climate(precipitation, start, end):
    """Function to integrate observed precipitation datasets at the annual level"""
    
    img_coll = ee.List([])
    for year in range(start, end+1):
        # get the precipitation img
        prec_img = precipitation \
            .filterDate(f'{year}-01-01', f'{year}-12-31') \
            .reduce(ee.Reducer.sum()) \
            .rename('clim')
        
        # convert to float
        con_img = ee.Image(year).float().rename('year')
        img = prec_img.addBands(con_img).set({'year': year})
        
        # append to the collection
        img_coll = img_coll.add(img)
        
    return ee.ImageCollection(img_coll)

def CalcNDVI(img):
    """compute the ndvi on renamed bands"""
    
    red = img.select('Red')
    nir = img.select('NIR')
    
    ndvi = nir.subtract(red) \
        .divide(nir.add(red)) \
        .multiply(10000) \
        .rename('ndvi') \
        .set('system:time_start', img.get('system:time_start'))
    
    return ndvi