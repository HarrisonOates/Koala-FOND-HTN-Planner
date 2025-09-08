import sys
import os
import subprocess

# Timeout in minutes
def solve(domain, problem, optional_flags, timeout=30):
    path = os.getcwd()
    parser_path = path + "/parser/pandaPIparser"
    grounder_path = path + "/grounder/pandaPIgrounder/"
    serilazer_path = path + "/serializer/"
    planner_path = path + "/planner/"
    # Parsing
    parsed = subprocess.run(
        [parser_path,
         path + f"/{domain}", path + f"/{problem}"],
         capture_output=True)
    print(parsed.stderr.decode("utf-8"))
    with open(grounder_path + "parsed.htn", "w+") as f:
        f.write(parsed.stdout.decode("utf-8"))
    # Grounding
    if os.path.isfile(grounder_path + "parsed.htn"):
        subprocess.run(
            [grounder_path + "pandaPIgrounder",
            grounder_path + "parsed.htn",
            serilazer_path + "result.sas+"], capture_output=True
        )
        os.remove(grounder_path + "parsed.htn")
    else:
        print(f"\t\tfailed to parse {problem}", file=sys.stderr)
        return
    # Serializing
    if os.path.isfile(serilazer_path + "result.sas+"):
        serialized = subprocess.run(
            ["python3", serilazer_path + "htn_parser.py",
            serilazer_path + "result.sas+", planner_path + "result.json"],
            capture_output=True)
        print(serialized.stderr.decode("utf-8"))
        os.remove(serilazer_path + "result.sas+")
    else:
        print(f"\t\tfailed to ground {problem}", file=sys.stderr)
        return
    # Search
    if os.path.isfile(planner_path + "result.json"):
        try:
            release_suffix = "target/release/planner"
            debug_suffix = "target/debug/planner"
            debug_mode = False
            if os.path.isfile(planner_path + release_suffix):
                print("Running in release mode")
                result = subprocess.run(
                    [planner_path + release_suffix, planner_path + "result.json"] + optional_flags,
                    capture_output=True, timeout= 60 * timeout)
            elif os.path.isfile(planner_path + debug_suffix):
                print("Release binary not available, using debug binary...")
                debug_mode = True
                result = subprocess.run(
                    [planner_path + debug_suffix, planner_path + "result.json"] + optional_flags,
                    # Print results to terminal when in debug mode
                    capture_output=False, timeout= 60 * timeout)
            else:
                print(f"No binary found in {planner_path + release_suffix} or {planner_path + debug_suffix}, exiting.")
                sys.exit(1)
            if not debug_mode:
                with open(path + f"/{problem}_solution_{''.join(optional_flags)}.txt", "x") as f:
                    f.write(result.stdout.decode("utf-8"))
        except subprocess.TimeoutExpired:
            print(f'\t\ttimeout for {problem}')
        os.remove(planner_path + "result.json")
    else:
        print(f"failed to serialize {problem}", file=sys.stderr)

if __name__ == "__main__":
    import sys
    domain = sys.argv[1]
    problem = sys.argv[2]
    fixed_flag = [] if len(sys.argv) < 4 else [sys.argv[3]]
    heuristic_flag = [] if len(sys.argv) < 5 else [sys.argv[4]]
    optional_flags = fixed_flag + heuristic_flag
    solve(domain, problem, optional_flags)
