import argparse
from flock import Flock


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--flock",
        type=str,
        default="./config/flock.yaml",
        help="Path to flock (population/run) config",
    )
    parser.add_argument(
        "--vote",
        dest="vote_cfg",
        type=str,
        default="./config/vote.yaml",
        help="Path to vote/task config",
    )
    parser.add_argument(
        "--llms",
        type=str,
        default="./config/llms.yaml",
        help="Path to llm registry config",
    )
    parser.add_argument(
        "vote_positional",
        type=str,
        nargs="?",
        help="Optional positional vote config path",
    )

    args = parser.parse_args()

    vote_path = args.vote_positional or args.vote_cfg

    flock = Flock(flock_config=args.flock, llm_config=args.llms)
    prediction_df = flock.vote(vote_config=vote_path)
    print(prediction_df)


if __name__ == "__main__":
    main()
