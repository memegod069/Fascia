import os
import json
import numpy as np
import sys

# Add project root to path to import m1_solver
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import m1_solver
import warp as wp

def run_test():
    golden_path = os.path.join(os.path.dirname(__file__), "golden_m1.json")
    
    # We will simulate 101 frames (frames 0 to 100) for the full M1 test
    num_test_frames = 101
    
    print(f"Running M1 solver for {num_test_frames} frames...")
    
    with wp.ScopedDevice("cpu"):
        results = m1_solver.run_solver(
            scene_json_path="scene.json",
            animation_json_path="animation.json",
            output_dir="m1_test_output",
            limit_frames=num_test_frames
        )
        
    if not os.path.exists(golden_path):
        print(f"Golden file not found. Generating new golden file at {golden_path}...")
        with open(golden_path, "w") as f:
            json.dump(results, f, indent=2)
        print("Golden file generated successfully. Run the test again to verify.")
        return True
        
    print(f"Loading golden file from {golden_path}...")
    with open(golden_path, "r") as f:
        golden_results = json.load(f)
        
    print("Comparing simulation results with golden file...")
    
    all_ok = True
    
    for obj_name, frames in results.items():
        if obj_name not in golden_results:
            print(f"FAIL: Object {obj_name} not found in golden results.")
            all_ok = False
            continue
            
        golden_frames = golden_results[obj_name]
        if len(frames) != len(golden_frames):
            print(f"FAIL: Object {obj_name} has mismatched frame count. Got {len(frames)}, expected {len(golden_frames)}.")
            all_ok = False
            continue
            
        for f_idx, frame_data in enumerate(frames):
            golden_frame_data = golden_frames[f_idx]
            
            arr_curr = np.array(frame_data)
            arr_gold = np.array(golden_frame_data)
            
            # Compute relative error
            diff = np.linalg.norm(arr_curr - arr_gold)
            denom = np.linalg.norm(arr_gold)
            rel_error = diff / denom if denom > 1e-9 else diff
            
            if rel_error > 1e-4:
                print(f"FAIL: Object {obj_name} Frame {f_idx} has mismatched positions! Rel error: {rel_error:.2e} (limit: 1.00e-04)")
                all_ok = False
            else:
                print(f"PASS: Object {obj_name} Frame {f_idx} matched. Rel error: {rel_error:.2e}")
                
    if all_ok:
        print("\n[PASS] M1 Solver Core golden-file test passed successfully!")
        return True
    else:
        print("\n[FAIL] M1 Solver Core golden-file test failed.")
        return False

if __name__ == "__main__":
    success = run_test()
    if not success:
        sys.exit(1)
