import os
import shutil

import supervisely as sly
from dataset_tools.convert import unpack_if_archive
from supervisely.io.fs import (
    file_exists,
    get_file_ext,
    get_file_name,
    get_file_name_with_ext,
    get_file_size,
)
from tqdm import tqdm

import src.settings as s


def convert_and_upload_supervisely_project(
    api: sly.Api, workspace_id: int, project_name: str
) -> sly.ProjectInfo:
    # Possible structure for bbox case. Feel free to modify as you needs.

    dataset_path = "/home/alex/DATASETS/TODO/trash_ICRA19/dataset"

    batch_size = 30
    images_ext = ".jpg"
    ann_ext = ".txt"

    def create_ann(image_path):
        labels = []

        seq_value = get_file_name(image_path).split("_")[0]
        seq = sly.Tag(seq_meta, value=seq_value)

        image_np = sly.imaging.image.read(image_path)[:, :, 0]
        img_height = image_np.shape[0]
        img_wight = image_np.shape[1]

        ann_path = image_path.replace(images_ext, ann_ext)

        if file_exists(ann_path):
            with open(ann_path) as f:
                content = f.read().split("\n")

                for curr_data in content:
                    if len(curr_data) != 0:
                        curr_data = list(map(float, curr_data.split(" ")))
                        obj_class = idx_to_class[int(curr_data[0])]

                        left = int((curr_data[1] - curr_data[3] / 2) * img_wight)
                        right = int((curr_data[1] + curr_data[3] / 2) * img_wight)
                        top = int((curr_data[2] - curr_data[4] / 2) * img_height)
                        bottom = int((curr_data[2] + curr_data[4] / 2) * img_height)
                        rectangle = sly.Rectangle(top=top, left=left, bottom=bottom, right=right)
                        label = sly.Label(rectangle, obj_class)
                        labels.append(label)

        return sly.Annotation(img_size=(img_height, img_wight), labels=labels, img_tags=[seq])

    plastic = sly.ObjClass("plastic", sly.Rectangle)
    bio = sly.ObjClass("bio", sly.Rectangle)
    rov = sly.ObjClass("rov", sly.Rectangle)

    idx_to_class = {0: plastic, 1: bio, 2: rov}

    seq_meta = sly.TagMeta("sequence", sly.TagValueType.ANY_STRING)

    project = api.project.create(workspace_id, project_name, change_name_if_conflict=True)
    meta = sly.ProjectMeta(obj_classes=[plastic, bio, rov], tag_metas=[seq_meta])
    api.project.update_meta(project.id, meta.to_json())

    for ds_name in os.listdir(dataset_path):

        curr_ds_path = os.path.join(dataset_path, ds_name)

        dataset = api.dataset.create(project.id, ds_name, change_name_if_conflict=True)

        images_names = [
            im_name for im_name in os.listdir(curr_ds_path) if get_file_ext(im_name) == images_ext
        ]

        progress = sly.Progress("Create dataset {}".format(ds_name), len(images_names))

        for images_names_batch in sly.batched(images_names, batch_size=batch_size):
            img_pathes_batch = [
                os.path.join(curr_ds_path, image_name) for image_name in images_names_batch
            ]

            img_infos = api.image.upload_paths(dataset.id, images_names_batch, img_pathes_batch)
            img_ids = [im_info.id for im_info in img_infos]

            anns = [create_ann(image_path) for image_path in img_pathes_batch]
            api.annotation.upload_anns(img_ids, anns)

            progress.iters_done_report(len(images_names_batch))

    return project
