import argparse
import os
import sys
import numpy as np
from multiprocessing.dummy import Pool as ThreadPool

try:
    import cv2
except ImportError:
    print("Error: OpenCV is required. Please run 'pip install opencv-python numpy'")
    sys.exit(1)

def hex_to_rgb_norm(hex_str):
    hex_str = hex_str.lstrip('#')
    if len(hex_str) != 6:
        print("Error: Color must be a 6-character hex code (e.g. #FFFFFF)")
        sys.exit(1)
    return tuple(int(hex_str[i:i+2], 16) / 255.0 for i in (0, 2, 4))

def get_dimensions(res_str, aspect_str):
    if 'x' in res_str.lower():
        try:
            w, h = map(int, res_str.lower().split('x'))
            return w, h
        except ValueError:
            print("Error: Invalid custom resolution format. Use WxH (e.g., 1280x720).")
            sys.exit(1)
    
    # Standard formats
    res_map = {'8k': 8192, '4k': 4096, '2k': 2048, '1k': 1024}
    if res_str.lower() not in res_map:
        print(f"Error: Unknown resolution '{res_str}'. Supported: 8k, 4k, 2k, 1k, or WxH.")
        sys.exit(1)
        
    base_dim = res_map[res_str.lower()]
    
    try:
        asp_w, asp_h = map(float, aspect_str.split(':'))
    except ValueError:
        print("Error: Invalid aspect ratio format. Use W:H (e.g., 16:9).")
        sys.exit(1)
        
    if asp_w >= asp_h:
        w = base_dim
        h = int(base_dim * (asp_h / asp_w))
    else:
        h = base_dim
        w = int(base_dim * (asp_w / asp_h))
        
    return w, h

def main():
    parser = argparse.ArgumentParser(description="Versatile Image Sequence Generator for Blender Masks/Textures.")
    parser.add_argument('--frames', type=int, required=True, help="Number of frames to generate.")
    parser.add_argument('--res', type=str, required=True, help="Resolution (e.g. 8k, 4k, 2k, 1k, 1280x720).")
    parser.add_argument('--name', type=str, required=True, help="Base name of the images.")
    
    parser.add_argument('--aspect', type=str, default="1:1", help="Aspect ratio (e.g. 1:1, 2:1). Default: 1:1")
    parser.add_argument('--type', type=str, default="png", choices=["jpeg", "png", "exr"], help="File type. Default: png")
    parser.add_argument('--bit', type=int, default=8, choices=[8, 16, 32], help="Color depth (8, 16, 32). Default: 8")
    parser.add_argument('--channels', type=str, default=None, choices=["rgb", "rgba", "bw"], help="Color channels. Default: rgba (rgb for jpeg)")
    parser.add_argument('--color', type=str, default="#000000", help="Hex color code (e.g. #FF0000). Default: #000000")
    parser.add_argument('--alpha', type=float, default=100, help="Alpha opacity (0-100). Default: 100")
    parser.add_argument('--out', type=str, default="output", help="Output directory. Default: 'output' folder in current directory")
    
    args = parser.parse_args()
    
    if args.type == "exr":
        try:
            import pyexr
        except ImportError:
            print("Error: EXR generation requires 'pyexr'. Please run 'pip install pyexr'")
            sys.exit(1)
            
    # 1. Defaults & Logic Overrides
    if args.channels is None:
        args.channels = "rgb" if args.type == "jpeg" else "rgba"
        
    # 2. Validation
    if args.type == "jpeg" and args.channels == "rgba":
        print("Error: JPEGs cannot have an alpha channel (rgba). Use 'rgb' or 'bw' instead.")
        sys.exit(1)
    
    if args.type == "jpeg" and args.bit != 8:
        print("Error: Standard JPEGs only support 8-bit color depth.")
        sys.exit(1)
        
    if args.type == "png" and args.bit == 32:
        print("Error: 32-bit float PNGs are not standard. Please use EXR for 32-bit depth, or 8/16-bit for PNG.")
        sys.exit(1)
        
    if args.type == "exr" and args.bit == 8:
        print("Error: EXR format is meant for high dynamic range (16-bit or 32-bit float). Please specify --bit 16 or --bit 32.")
        sys.exit(1)
        
    # 3. Calculate Dimensions
    width, height = get_dimensions(args.res, args.aspect)
    
    # 4. Color & Alpha Math
    r_norm, g_norm, b_norm = hex_to_rgb_norm(args.color)
    a_norm = max(0.0, min(100.0, args.alpha)) / 100.0
    
    if args.channels == "bw":
        luma = 0.299 * r_norm + 0.587 * g_norm + 0.114 * b_norm
        val_cv2 = [luma]
        val_exr = [luma]
    elif args.channels == "rgb":
        val_cv2 = [b_norm, g_norm, r_norm] # BGR for OpenCV
        val_exr = [r_norm, g_norm, b_norm] # RGB for pyexr
    elif args.channels == "rgba":
        val_cv2 = [b_norm, g_norm, r_norm, a_norm]
        val_exr = [r_norm, g_norm, b_norm, a_norm]
        
    active_val = val_exr if args.type == "exr" else val_cv2
        
    # Apply Bit Depth
    if args.type == "exr":
        if args.bit == 16:
            pixel_val = np.array(active_val, dtype=np.float16)
            img_dtype = np.float16
        else:
            pixel_val = np.array(active_val, dtype=np.float32)
            img_dtype = np.float32
    elif args.bit == 8:
        pixel_val = np.array([v * 255 for v in active_val], dtype=np.uint8)
        img_dtype = np.uint8
    elif args.bit == 16:
        pixel_val = np.array([v * 65535 for v in active_val], dtype=np.uint16)
        img_dtype = np.uint16
        
    # 5. Create Base Image Array (Allocate once)
    print(f"Allocating base image array ({width}x{height}, {args.bit}-bit {args.channels.upper()})...")
    img = np.zeros((height, width, len(pixel_val)), dtype=img_dtype)
    img[:] = pixel_val
    
    out_dir = args.out if args.out else "output" 
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)
        
    pad_len = len(str(args.frames))
    
    # 6. Writing Function
    def write_frame(i):
        frame_idx = str(i).zfill(pad_len)
        filename = f"{args.name}_{args.res}_{frame_idx}.{args.type}"
        filepath = os.path.join(out_dir, filename)
        
        if args.type == "exr":
            import pyexr
            pyexr.write(filepath, img)
        else:
            cv2.imwrite(filepath, img)
            
        return filename

    # 7. Multiprocessing Pool execution
    print(f"Generating {args.frames} frames in '{out_dir}'...")
    
    pool = ThreadPool(os.cpu_count())
    
    for i, _ in enumerate(pool.imap_unordered(write_frame, range(1, args.frames + 1)), 1):
        sys.stdout.write(f"\rProgress: {i}/{args.frames} frames saved.")
        sys.stdout.flush()
        
    pool.close()
    pool.join()
    
    print("\nGeneration complete!")

if __name__ == "__main__":
    main()
