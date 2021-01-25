import ee
import geemap
from ipywidgets import Output
import ipyvuetify as v

from component import parameter as pm

from .gdrive import gdrive
from .gee import wait_for_completion
from .download import digest_tiles
from .integration import * 
from .productivity import *
from .soil_organic_carbon import *
from .land_cover import *

ee.Initialize()

def download_maps(aoi_io, io, output):
    
    # get the export scale 
    scale = 10 if 'Sentinel 2' in io.sensors else 30
        
    # create the export path
    land_cover_desc = f'{aoi_io.get_aoi_name()}_land_cover'
    soc_desc = f'{aoi_io.get_aoi_name()}_soc'
    productivity_desc = f'{aoi_io.get_aoi_name()}_productivity'
    indicator_15_3_1_desc = f'{aoi_io.get_aoi_name()}_indicator_15_3_1'
        
    # load the drive_handler
    drive_handler = gdrive()
        
    # download all files
    downloads = drive_handler.download_to_disk(land_cover_desc, io.land_cover, aoi_io, output)
    downloads = drive_handler.download_to_disk(soc_desc, io.soc, aoi_io, output)
    downloads = drive_handler.download_to_disk(productivity_desc, io.productivity, aoi_io, output)
    downloads = drive_handler.download_to_disk(indicator_15_3_1_desc, io.indicator_15_3_1, aoi_io, output)
        
    # I assume that they are always launch at the same time 
    # If not it's going to crash
    if downloads:
        wait_for_completion([land_cover_desc, soc_desc, productivity_desc, indicator_15_3_1_desc], output)
    output.add_live_msg('GEE tasks completed', 'success') 
        
    # digest the tiles
    digest_tiles(aoi_io, land_cover_desc, pm.result_dir, output, pm.result_dir.joinpath(f'{land_cover_desc}_merge.tif'))
    digest_tiles(aoi_io, soc_desc, pm.result_dir, output, pm.result_dir.joinpath(f'{soc_desc}_merge.tif'))
    digest_tiles(aoi_io, productivity_desc, pm.result_dir, output, pm.result_dir.joinpath(f'{productivity_desc}_merge.tif'))
    digest_tiles(aoi_io, indicator_15_3_1_desc, pm.result_dir, output, pm.result_dir.joinpath(f'{indicator_15_3_1_desc}_merge.tif'))
        
    # remove the files from drive
    drive_handler.delete_files(drive_handler.get_files(land_cover_desc))
    drive_handler.delete_files(drive_handler.get_files(soc_desc))
    drive_handler.delete_files(drive_handler.get_files(productivity_desc))
    drive_handler.delete_files(drive_handler.get_files(indicator_15_3_1_desc))
        
    #display msg 
    output.add_live_msg('Download complete', 'success')

    return

def display_maps(aoi_io, io, m, output):
    
    m.zoom_ee_object(aoi_io.get_aoi_ee().geometry())
        
    # add the layers 
    geom = aoi_io.get_aoi_ee().geometry().bounds()
    m.addLayer(io.productivity.clip(geom), pm.viz, 'productivity')
    m.addLayer(io.land_cover.select('degredation').clip(geom), pm.viz, 'land_cover')
    m.addLayer(io.soc.clip(geom), pm.viz, 'soil_organic_carbon')
    m.addLayer(io.indicator_15_3_1.clip(geom), pm.viz, 'indicator_15_3_1')
        
    # add the aoi on the map 
    m.addLayer(aoi_io.get_aoi_ee(), {'color': v.theme.themes.dark.info}, 'aoi')
    
    return 

def compute_indicator_maps(aoi_io, io, output):
    
    # compute intermediary maps 
    ndvi_int, climate_int = integrate_ndvi_climate(aoi_io, io, output)
    prod_trajectory = productivity_trajectory(io, ndvi_int, climate_int, output)
    prod_performance = productivity_performance(aoi_io, io, ndvi_int, climate_int, output)
    prod_state = productivity_state(aoi_io, io, ndvi_int, climate_int, output) 
        
    # compute result maps 
    io.land_cover = land_cover(io, aoi_io, output)
    io.soc = soil_organic_carbon(io, aoi_io, output)
    io.productivity = productivity_final(prod_trajectory, prod_performance, prod_state, output)
    
    # sump up in a map
    io.indicator_15_3_1 = indicator_15_3_1(io.productivity, io.land_cover, io.soc, output)

    return 

def compute_zonal_analysis(aoi_io, io, output):
    
    indicator_15_3_1_stats = pm.result_dir.joinpath(f'{aoi_io.get_aoi_name()}_indicator_15_3_1.csv')
        
    output_widget = Output()
    output.add_msg(output_widget)
        
    with output_widget:
        geemap.zonal_statistics_by_group(
            in_value_raster = io.indicator_15_3_1,
            in_zone_vector = aoi_io.get_aoi_ee(),
            out_file_path = indicator_15_3_1_stats,
            statistics_type = "PERCENTAGE",
            decimal_places=2,
            tile_scale=1.0
        )
            
    return indicator_15_3_1_stats
    

def indicator_15_3_1(productivity, landcover, soc, output):
    
    landcover = landcover.select('degredation')
    
    indicator = ee.Image(pm.int_16_min) \
        .where(productivity.eq(1).And(landcover.eq(1)).And(soc.eq(1)),1) \
        .where(productivity.eq(1).And(landcover.eq(1)).And(soc.eq(0)),1) \
        .where(productivity.eq(1).And(landcover.eq(1)).And(soc.eq(-1)),-1) \
        .where(productivity.eq(1).And(landcover.eq(0)).And(soc.eq(1)),1) \
        .where(productivity.eq(1).And(landcover.eq(0)).And(soc.eq(0)),1) \
        .where(productivity.eq(1).And(landcover.eq(0)).And(soc.eq(-1)),-1) \
        .where(productivity.eq(1).And(landcover.eq(-1)).And(soc.eq(1)),-1) \
        .where(productivity.eq(1).And(landcover.eq(-1)).And(soc.eq(0)),-1) \
        .where(productivity.eq(1).And(landcover.eq(-1)).And(soc.eq(-1)),-1) \
        .where(productivity.eq(0).And(landcover.eq(1)).And(soc.eq(1)),1) \
        .where(productivity.eq(0).And(landcover.eq(1)).And(soc.eq(0)),1) \
        .where(productivity.eq(0).And(landcover.eq(1)).And(soc.eq(-1)),-1) \
        .where(productivity.eq(0).And(landcover.eq(0)).And(soc.eq(1)),1) \
        .where(productivity.eq(0).And(landcover.eq(0)).And(soc.eq(0)),0) \
        .where(productivity.eq(0).And(landcover.eq(0)).And(soc.eq(-1)),-1) \
        .where(productivity.eq(0).And(landcover.eq(-1)).And(soc.eq(1)),-1) \
        .where(productivity.eq(0).And(landcover.eq(-1)).And(soc.eq(0)),-1) \
        .where(productivity.eq(0).And(landcover.eq(-1)).And(soc.eq(-1)),-1) \
        .where(productivity.eq(-1).And(landcover.eq(1)).And(soc.eq(1)),-1) \
        .where(productivity.eq(-1).And(landcover.eq(1)).And(soc.eq(0)),-1) \
        .where(productivity.eq(-1).And(landcover.eq(1)).And(soc.eq(-1)),-1) \
        .where(productivity.eq(-1).And(landcover.eq(0)).And(soc.eq(1)),-1) \
        .where(productivity.eq(-1).And(landcover.eq(0)).And(soc.eq(0)),-1) \
        .where(productivity.eq(-1).And(landcover.eq(0)).And(soc.eq(-1)),-1) \
        .where(productivity.eq(-1).And(landcover.eq(-1)).And(soc.eq(1)),-1) \
        .where(productivity.eq(-1).And(landcover.eq(-1)).And(soc.eq(0)),-1) \
        .where(productivity.eq(-1).And(landcover.eq(-1)).And(soc.eq(-1)),-1) 
    
    output = indicator \
        .unmask(pm.int_16_min) \
        .int16()
    
    return output