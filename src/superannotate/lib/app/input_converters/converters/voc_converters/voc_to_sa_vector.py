"""
VOC to SA conversion method
"""
import threading

import cv2
import numpy as np
from superannotate.logger import get_default_logger

from ....common import tqdm_converter
from ....common import write_to_json
from ..sa_json_helper import _create_sa_json
from ..sa_json_helper import _create_vector_instance
from .voc_helper import _get_image_metadata
from .voc_helper import _get_voc_instances_from_xml
from .voc_helper import _iou

logger = get_default_logger()


def _generate_polygons(object_mask_path):
    segmentation = []

    object_mask = cv2.imread(str(object_mask_path), cv2.IMREAD_GRAYSCALE)

    object_unique_colors = np.unique(object_mask)

    index = 1
    groupId = 0
    for unique_color in object_unique_colors:
        if unique_color in (0, 220):
            continue

        mask = np.zeros_like(object_mask)
        mask[object_mask == unique_color] = 255
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        segment = []
        if len(contours) > 1:
            for contour in contours:
                segment.append(contour.flatten().tolist())
            groupId = index
            index += 1
        else:
            segment.append(contours[0].flatten().tolist())
            groupId = 0

        segmentation.append((segment, groupId))

    return segmentation


def _generate_instances(polygon_instances, voc_instances):
    instances = []
    for polygon, group_id in polygon_instances:
        ious = []
        if len(polygon) > 1:
            temp = []
            for poly in polygon:
                temp += poly
        else:
            temp = polygon[0]
        bbox_poly = [min(temp[::2]), min(temp[1::2]), max(temp[::2]), max(temp[1::2])]
        for _, bbox in voc_instances:
            ious.append(_iou(bbox_poly, bbox))
        ind = np.argmax(ious)
        for poly in polygon:
            class_name = list(voc_instances[ind][0].keys())[0]
            attributes = voc_instances[ind][0][class_name]
            instances.append(
                {
                    "className": class_name,
                    "polygon": poly,
                    "bbox": voc_instances[ind][1],
                    "groupId": group_id,
                    "classAttributes": attributes,
                }
            )
    return instances


def voc_instance_segmentation_to_sa_vector(voc_root, output_dir):
    classes = []
    object_masks_dir = voc_root / "SegmentationObject"
    annotation_dir = voc_root / "Annotations"
    file_list = list(object_masks_dir.glob("*"))
    if not file_list:
        logger.warning(
            "You need to have both 'Annotations' and 'SegmentationObject' directories to be able to convert."
        )

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
    for filename in file_list:
        polygon_instances = _generate_polygons(object_masks_dir / filename.name)
        voc_instances = _get_voc_instances_from_xml(annotation_dir / filename.name)
        for class_, _ in voc_instances:
            classes.append(class_)

        maped_instances = _generate_instances(polygon_instances, voc_instances)
        sa_instances = []
        for instance in maped_instances:
            sa_obj = _create_vector_instance(
                "polygon",
                instance["polygon"],
                {},
                instance["classAttributes"],
                instance["className"],
            )
            sa_instances.append(sa_obj)

        images_converted.append(filename)
        file_name, height, width = _get_image_metadata(annotation_dir / filename.name)
        file_path = f"{file_name}___objects.json"
        sa_metadata = {"name": str(filename), "height": height, "width": width}
        sa_json = _create_sa_json(sa_instances, sa_metadata)
        write_to_json(output_dir / file_path, sa_json)

    finish_event.set()
    tqdm_thread.join()
    return classes


def voc_object_detection_to_sa_vector(voc_root, output_dir):
    classes = []
    annotation_dir = voc_root / "Annotations"
    file_list = list(annotation_dir.glob("*"))
    if not file_list:
        logger.warning("'Annotations' directory is empty")

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

    for filename in file_list:
        voc_instances = _get_voc_instances_from_xml(annotation_dir / filename.name)
        sa_instances = []
        for class_, bbox in voc_instances:
            class_name = list(class_.keys())[0]
            classes.append(class_)

            points = (bbox[0], bbox[1], bbox[2], bbox[3])
            sa_obj = _create_vector_instance(
                "bbox", points, {}, class_[class_name], class_name
            )
            sa_instances.append(sa_obj)

        images_converted.append(filename)
        file_name, height, width = _get_image_metadata(annotation_dir / filename.name)
        file_path = f"{file_name}___objects.json"
        sa_metadata = {"name": str(filename), "height": height, "width": width}
        sa_json = _create_sa_json(sa_instances, sa_metadata)
        write_to_json(output_dir / file_path, sa_json)

    finish_event.set()
    tqdm_thread.join()
    return classes
