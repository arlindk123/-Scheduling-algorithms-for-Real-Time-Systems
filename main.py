from algorithms import (
    ldf_single_node,
    edf_single_node,
    edf_multinode_no_delay,
    ll_multinode_no_delay,
    ldf_multinode_no_delay,
)
import os
import json

script_dir = os.path.dirname(__file__)
input_models_dir = os.path.join(script_dir, "../test/input_models")


def main():
    with open("tests/input_models/Prof_Example.json", mode="r") as f:
        data = json.load(f)
    application_data = data.get("application")
    platform_data = data.get("platform")

    ldf = ldf_single_node(application_data)
    edf = edf_single_node(application_data)
    edf_multi = edf_multinode_no_delay(application_data, platform_data)
    ldf_multi = ldf_multinode_no_delay(application_data, platform_data)
    ll = ll_multinode_no_delay(application_data, platform_data)

    print(f"ldf single node: {json.dumps(ldf, indent=2)}")
    print(f"edf single node: {json.dumps(edf, indent=2)}")
    print(f"ll multi node: {json.dumps(ll, indent=2)}")
    print(f"ldf multi node: {json.dumps(ldf_multi, indent=2)}")
    print(f"edf multi node: {json.dumps(edf_multi, indent=2)}")


if __name__ == "__main__":
    main()
