"""
VoTT to SA conversion method
"""
import json
import threading

from superannotate.logger import get_default_logger

from ....common import tqdm_converter
from ....common import write_to_json
from ..sa_json_helper import _create_sa_json
from ..sa_json_helper import _create_vector_instance

logger = get_default_logger()


def vott_to_sa(file_list, task, output_dir):
    classes = []
    if task == "object_detection":
        instance_types = ["RECTANGLE"]
    elif task == "instance_segmentation":
        instance_types = ["POLYGON"]
    elif task == "vector_annotation":
        instance_types = ["RECTANGLE", "POLYGON"]

    images_converted = []
    images_not_converted = []
    finish_event = threading.Event()
    tqdm_thread = threading.Thread(
        target=tqdm_converter,
        args=(len(file_list), images_converted, images_not_converted, finish_event),
        daemon=True,
    )
    logger.info("Converting to SuperAnnotate JSON format")
    tqdm_thread.start()
    for json_file in file_list:
        json_data = json.load(open(json_file))
        file_name = "%s___objects.json" % json_data["asset"]["name"]
        sa_metadata = {
            "name": json_data["asset"]["name"],
            "width": json_data["asset"]["size"]["width"],
            "height": json_data["asset"]["size"]["height"],
        }

        instances = json_data["regions"]
        sa_instances = []
        for instance in instances:
            for tag in instance["tags"]:
                classes.append(tag)

            if instance["type"] in instance_types:
                if instance["type"] == "RECTANGLE":
                    instance_type = "bbox"
                    points = (
                        instance["boundingBox"]["left"],
                        instance["boundingBox"]["top"],
                        instance["boundingBox"]["left"]
                        + instance["boundingBox"]["width"],
                        instance["boundingBox"]["top"]
                        + instance["boundingBox"]["height"],
                    )
                elif instance["type"] == "POLYGON":
                    instance_type = "polygon"
                    points = []
                    for point in instance["points"]:
                        points.append(point["x"])
                        points.append(point["y"])

                sa_obj = _create_vector_instance(
                    instance_type, points, {}, [], instance["tags"][0]
                )
                sa_instances.append(sa_obj.copy())
        images_converted.append(json_data["asset"]["name"])
        sa_json = _create_sa_json(sa_instances, sa_metadata)
        write_to_json(output_dir / file_name, sa_json)
    finish_event.set()
    tqdm_thread.join()
    return set(classes)
