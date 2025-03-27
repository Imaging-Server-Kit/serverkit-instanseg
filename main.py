"""
Algorithm server definition.
Documentation: https://github.com/Imaging-Server-Kit/cookiecutter-serverkit
"""

from typing import List, Literal, Type
from pathlib import Path
import numpy as np
from pydantic import BaseModel, Field, field_validator
import uvicorn
import skimage.io
import imaging_server_kit as serverkit
from instanseg import InstanSeg


class Parameters(BaseModel):
    """Defines the algorithm parameters"""

    image: str = Field(
        ...,
        title="Image",
        description="Input image (2D, RGB).",
        json_schema_extra={"widget_type": "image"},
    )

    model_name: Literal["fluorescence_nuclei_and_cells", "brightfield_nuclei"] = Field(
        default="fluorescence_nuclei_and_cells",
        title="Model",
        description="Segmentation model",
        json_schema_extra={"widget_type": "dropdown"},
    )

    pixel_size: float = Field(
        default=0.5,
        title="Pixel size (um/px)",
        description="Pixel size (um/px)",
        ge=0.1,
        le=10.0,
        json_schema_extra={
            "widget_type": "float",
            "step": 0.05,
        },
    )

    @field_validator("image", mode="after")
    def decode_image_array(cls, v) -> np.ndarray:
        image_array = serverkit.decode_contents(v)
        if image_array.ndim not in [2, 3]:
            raise ValueError("Array has the wrong dimensionality.")
        return image_array


class Server(serverkit.Server):
    def __init__(
        self,
        algorithm_name: str = "instanseg",
        parameters_model: Type[BaseModel] = Parameters,
    ):
        super().__init__(algorithm_name, parameters_model)

    def run_algorithm(
        self, image: np.ndarray, model_name: str, pixel_size: float, **kwargs
    ) -> List[tuple]:
        """Runs the algorithm."""
        instanseg_brightfield = InstanSeg(
            model_name, image_reader="tiffslide", verbosity=1
        )

        segmentation, image_tensor = instanseg_brightfield.eval_small_image(
            image, pixel_size
        )
        segmentation = segmentation[0].cpu().numpy()

        segmentation = segmentation[::-1]  # Apparently the channel axis needs to be inverted?

        segmentation_params = {"name": f"InstanSeg ({model_name})"}

        if model_name == "fluorescence_nuclei_and_cells":
            # The fluorescence model returns a 3D segmentation array for the 2D+c image
            return [(segmentation, segmentation_params, "mask3d")]
        else:
            # The brightfield nuclei model can be returned as Shapely features
            segmentation = np.squeeze(segmentation)
            return [(segmentation, segmentation_params, "instance_mask")]

    def load_sample_images(self) -> List["np.ndarray"]:
        """Loads one or multiple sample images."""
        image_dir = Path(__file__).parent / "sample_images"
        images = [skimage.io.imread(image_path) for image_path in image_dir.glob("*")]
        return images


server = Server()
app = server.app

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
