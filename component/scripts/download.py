import time

import rasterio as rio
from rasterio.merge import merge

from .gdrive import gdrive

def digest_tiles(aoi_io, filename, result_dir, output, tmp_file):
    
    drive_handler = gdrive()
    files = drive_handler.get_files(filename)
    
    # if no file, it means that the download had failed
    if not len(files):
        raise Exception('no files in Gdrive')
        
    drive_handler.download_files(files, result_dir)
    
    pathname = f'{filename}*.tif'
    
    files = [file for file in result_dir.glob(pathname)]
        
    #run the merge process
    output.add_live_msg("merge tiles")
    time.sleep(2)
    
    #manual open and close because I don't know how many file there are
    sources = [rio.open(file) for file in files]

    data, output_transform = merge(sources)
    
    out_meta = sources[0].meta.copy()    
    out_meta.update(
        driver    = "GTiff",
        height    =  data.shape[1],
        width     =  data.shape[2],
        transform = output_transform,
        compress  = 'lzw'
    )
    
    with rio.open(tmp_file, "w", **out_meta) as dest:
        dest.write(data)
    
    # manually close the files
    [src.close() for src in sources]
    
    # delete local files
    [file.unlink() for file in files]
    
    return