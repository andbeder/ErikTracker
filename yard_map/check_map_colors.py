#!/usr/bin/env python3
from PIL import Image
import numpy as np
import sys

if len(sys.argv) > 1:
    filename = sys.argv[1]
else:
    filename = 'test_2m_points.png'

img = Image.open(filename)
arr = np.array(img)
print(f'Map analysis for {filename}:')
print(f'  Shape: {arr.shape}')
print(f'  Mean color: R={arr[:,:,0].mean():.1f}, G={arr[:,:,1].mean():.1f}, B={arr[:,:,2].mean():.1f}')

# Count gray pixels
gray50_pixels = np.sum((arr[:,:,0] == 50) & (arr[:,:,1] == 50) & (arr[:,:,2] == 50))
print(f'  Gray(50) pixels: {gray50_pixels} / {640*360} ({gray50_pixels/(640*360)*100:.1f}%)')
print(f'  Colored pixels: {640*360 - gray50_pixels} ({(640*360 - gray50_pixels)/(640*360)*100:.1f}%)')

# Find colored pixels
not_gray = ~((arr[:,:,0] == 50) & (arr[:,:,1] == 50) & (arr[:,:,2] == 50))
colored_pixels = np.where(not_gray)

if len(colored_pixels[0]) > 0:
    print('\nSample colored pixels:')
    for i in range(min(10, len(colored_pixels[0]))):
        y, x = colored_pixels[0][i], colored_pixels[1][i]
        print(f'  ({x},{y}): RGB({arr[y,x,0]}, {arr[y,x,1]}, {arr[y,x,2]})')
        
    # Get average of colored pixels only
    colored_only = arr[not_gray]
    print(f'\nAverage of colored pixels only:')
    print(f'  R={colored_only[:,0].mean():.1f}, G={colored_only[:,1].mean():.1f}, B={colored_only[:,2].mean():.1f}')