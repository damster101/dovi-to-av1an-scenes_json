import json
import subprocess

source = "source.mkv"
rpu = f"{source}.rpu"


def ask_yes_no(prompt, default="no"):
    answer = input(prompt + " ").strip().lower()
    if not answer:
        answer = default.lower()
    return answer.startswith("y")


def extract_rpu(source):
    if ask_yes_no(
            "\nDo you want to extract the RPU from video source? (yes/No):",
            default="no"):
        rpu_compat = f"{source}_compat.rpu"
        print("Extracting RPU...")
        cmd = f"""
        ffmpeg -i "{source}" -c:v copy -bsf hevc_mp4toannexb -f hevc - | 
        tee >(dovi_tool -m 2 -c extract-rpu -o "{rpu_compat}" -) | 
        dovi_tool extract-rpu -o "{rpu}" -
        """
        subprocess.run(["bash", "-c", cmd.strip()], check=True)
    else:
        print("Skipping RPU extraction")

    if ask_yes_no(
            "\nDo you want to plot dynamic tonemapping metadata? (yes/No):",
            default="no"):
        subprocess.run(["dovi_tool", "plot", "-o", f"{rpu}.png", rpu],
                       check=True)
    else:
        print("Skipping plotting of tonemapping metadata")

    if ask_yes_no("\nDo you want to export all metadata to JSON? (yes/No):",
                  default="no"):
        subprocess.run(["dovi_tool", "export", "-d", f"all={rpu}.json", rpu],
                       check=True)
    else:
        print("Skipping full export to JSON")


def get_total_frames(rpu):
    l5_json = f"{rpu}-level5.json"

    print("\nExport L5 metadata to JSON")
    subprocess.run(["dovi_tool", "export", "-d", f"level5={l5_json}", rpu],
                   check=True)

    print("\nParsing L5 JSON for total number of frames...")
    with open(l5_json, 'r') as f:
        data = json.load(f)
    edits = data.get("edits", {})
    if not edits:
        raise ValueError("No edits found in L5 JSON.")
    key = next(iter(edits.keys()))
    try:
        last_frame = int(key.split("-")[1])
    except (IndexError, ValueError) as e:
        raise ValueError("Unexpected format in edit key") from e

    return last_frame + 1


def generate_scenes_json(input_file, output_file, total_frames,
                         max_scene_length):
    print(f"\nGenerate {output_file} for Av1an")

    #print("Extracting scene cuts")
    subprocess.run(["dovi_tool", "export", "-d", f"scenes={input_file}", rpu],
                   check=True)

    with open(input_file, 'r') as f:
        numbers = [int(line.strip()) for line in f if line.strip()]

    if not numbers or numbers[-1] != total_frames:
        numbers.append(total_frames)

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

    scenes = [{
        "start_frame": interpolated_numbers[i],
        "end_frame": interpolated_numbers[i + 1],
        "zone_overrides": None
    } for i in range(len(interpolated_numbers) - 1)]

    data = {"scenes": scenes, "frames": total_frames}
    with open(output_file, 'w') as f:
        json.dump(data, f, indent=2)

    print(f"Scenes JSON written to {output_file}")


print("WARNING: Run from local folder!")
input("Press Enter to continue.")

extract_rpu(source)

total_frames = get_total_frames(rpu)
print(f"Total number of frames: {total_frames}")

max_scene_length_str = input(
    "\nEnter max scene length (in frames, leave empty for no limit): ").strip(
    )
try:
    max_scene_length = int(max_scene_length_str) if max_scene_length_str else 0
except ValueError:
    print("Invalid input, using no limit.")
    max_scene_length = 0

scenes_json_filename = f"scenes-max{max_scene_length}.json" if max_scene_length > 0 else "scenes.json"
generate_scenes_json(f"{rpu}-scenes.txt", scenes_json_filename, total_frames,
                     max_scene_length)
