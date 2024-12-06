import json
import os
import subprocess
import vapoursynth as vs

source = ("source.mkv")

input("WARNING: Run from local folder!\nPress Enter to continue.")


def extract_rpu(source):
    rpu_output = f"{source}.rpu"

    extract_rpu = input(
        "Do you want to extract the RPU? (yes/No): ").lower().strip()
    if extract_rpu == "yes":
        try:
            print("Extracting RPU...")
            subprocess.run(
                f'ffmpeg -i "{source}" -c:v copy -bsf hevc_mp4toannexb -f hevc - | '
                f'dovi_tool -m 2 -c extract-rpu -i - -o "{rpu_output}"',
                shell=True,
                check=True)
        except subprocess.CalledProcessError as e:
            print(f"Error extracting RPU: {e}")
    else:
        print("Skipping RPU extraction")

    rpu_plot = input(
        "Do you want to plot dynamic tonemapping metadata? (Yes/no): ").lower(
        ).strip()
    if rpu_plot == "no":
        print("Skipping plotting of tonemapping metadata")
    else:
        try:
            print("Plotting...")
            subprocess.run(
                f'dovi_tool plot -i "{rpu_output}" -o "{rpu_output}.png"',
                shell=True,
                check=True)
        except subprocess.CalledProcessError as e:
            print(f"Error plotting dynamic tonemapping metadata from RPU: {e}")

    rpu_scenes = input("Do you want to extract scene cuts from RPU? (Yes/no): "
                       ).lower().strip()
    if rpu_scenes == "no":
        print("Skipping scene cut extraction")
    else:
        try:
            print("Extracting scene cuts...")
            subprocess.run(f'dovi_tool export -d scenes -i "{rpu_output}"',
                           shell=True,
                           check=True)
        except subprocess.CalledProcessError as e:
            print(f"Error extracting scene cuts from RPU: {e}")


def get_total_frames(source, method):
    if method == 'a':
        if os.path.exists(f"{source}.ffindex"):
            print(
                f'Existing index file found: "{source}.ffindex". Skipping indexing.'
            )
        else:
            try:
                subprocess.run(f"ffmsindex '{source}'", shell=True, check=True)
            except Exception as e:
                print(f"Error during indexing: {e}")

        try:
            clip = vs.core.ffms2.Source(source)
            return clip.num_frames
        except Exception as e:
            print(f"Error using ffms2: {e}")
            return None

    elif method == 'b':
        try:
            clip = vs.core.lsmas.LWLibavSource(source)
            return clip.num_frames
        except Exception as e:
            print(f"Error using lsmash: {e}")
            return None

    elif method == 'c':
        try:
            clip = vs.core.bs.VideoSource(source)
            return clip.num_frames
        except Exception as e:
            print(f"Error using bestsource: {e}")
            return None

    elif method.isdigit():
        return int(method)

    return None


def generate_scenes_json(input_file, output_file, total_frames,
                         max_scene_length):
    print(f"Generating {output_file} for Av1an")
    try:
        with open(input_file, 'r') as f:
            numbers = [int(line.strip()) for line in f]

        # Ensure total_frames is an integer
        total_frames = int(total_frames)

        # Include the final frame (total_frames) as the last endpoint
        if numbers[-1] != total_frames:
            numbers.append(total_frames)

        # If max_scene_length is 0, use the original numbers without interpolation
        if max_scene_length > 0:
            interpolated_numbers = []
            for i in range(len(numbers) - 1):
                interpolated_numbers.append(numbers[i])
                diff = numbers[i + 1] - numbers[i]
                num_interpolations = max(0, (diff // max_scene_length) - 1)
                if num_interpolations > 0:
                    step = diff / (num_interpolations + 1)
                    for j in range(1, num_interpolations + 1):
                        interpolated_numbers.append(numbers[i] + int(step * j))
            interpolated_numbers.append(numbers[-1])
        else:
            interpolated_numbers = numbers

        # Generate scene data
        scenes = [{
            "start_frame": interpolated_numbers[i],
            "end_frame": interpolated_numbers[i + 1],
            "zone_overrides": None
        } for i in range(len(interpolated_numbers) - 1)]

        data = {"scenes": scenes, "frames": total_frames}

        with open(output_file, 'w') as f:
            json.dump(data, f, indent=2)

    except FileNotFoundError:
        print(f"Error: {input_file} not found.")
    except Exception as e:
        print(f"An error occurred while generating JSON: {e}")


extract_rpu(source)

while True:
    method = input(
        """To get the total number of frames, either choose an indexing method with:
    a for ffms2 (Default, just press Enter)
    b for lsmash
    c for bestsource
or enter the total number of frames manually: """).lower().strip() or 'a'
    total_frames = get_total_frames(source, method)
    if total_frames is not None:
        print(f"Total frames: {total_frames}")
        break
    print("Invalid input. Please try again.")

max_scene_length = int(
    input("Enter max scene length (in frames, leave empty for no limit): ")
    or 0)

scenes_json_filename = f"scenes-max{max_scene_length}.json" if max_scene_length > 0 else "scenes.json"
generate_scenes_json("RPU_scenes.txt", scenes_json_filename, total_frames,
                     max_scene_length)
