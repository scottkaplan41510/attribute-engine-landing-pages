"""Run one step: waf <step> <site>, where <site> is a folder in config/."""

import argparse

from . import capture, example, live, pipeline


def main():
    parser = argparse.ArgumentParser(prog="waf")
    parser.add_argument("step", choices=["capture-live", "capture-archive", "backfill-headlines", "reshoot-archive", "count-elements", "run", "sample", "example"])
    parser.add_argument("client", help="a folder in config/, such as example")
    args = parser.parse_args()
    if args.step == "capture-live":
        capture.capture_live(args.client)
    elif args.step == "capture-archive":
        capture.capture_archive(args.client)
    elif args.step == "backfill-headlines":
        print(capture.backfill_headlines(args.client))
    elif args.step == "reshoot-archive":
        capture.reshoot_archive(args.client)
    elif args.step == "count-elements":
        print(capture.count_page_elements(args.client))
    elif args.step == "sample":
        live.publish_sample(args.client)
    elif args.step == "example":
        result = example.build(args.client)
        print(f"{len(result['pages'])} illustrative pages written to the viewer", flush=True)
    elif args.step == "run":
        pipeline.run(args.client)


if __name__ == "__main__":
    main()
