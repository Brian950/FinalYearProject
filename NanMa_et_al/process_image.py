import cv2
import glob
import numpy as np
from NanMa_et_al.hsv_mask import HSVMask
from Common_Tools.line import Line
from Common_Tools.image_manipulation import Manipulation
from Common_Tools.draw_lane import DrawLane

SOBEL = True
img_size = (854, 360)

lane_params = {'saturation': 100, 'light_yellow': 60, 'light_white': 195,
               'gradient': (0.7, 1.5), 'x_thresh': 20, 'magnitude': 40}
lane_finder = HSVMask(lane_params)

left_lane = False
right_lane = False

left_line = Line()
right_line = Line()

sharp_kernel = np.array([[-1, -1, -1],
                         [-1, 9, -1],
                         [-1, -1, -1]])


def process(frame, mtx=None, dist=None, selection=None):

    image = crop(frame, 0, 360, 0, 854)

    # mtx set to None temporarily due to issue with distort leaving black pixels.
    mtx = None
    if mtx is not None and dist is not None:
        view = undistort(image, mtx, dist)
    else:
        view = image

    man = Manipulation(selection)
    src, dst = man.get_perspective_matrix()

    transform = man.perspective_transform(view, src, dst, img_size)

    # Classification of light intensity
    gray = cv2.cvtColor(transform, cv2.COLOR_RGB2GRAY)
    gray_mean_val = np.mean(gray)

    #Pixel gray value
    if gray_mean_val > 150:
        # High light intensity = gray equalisation
        eq_image = gray_equalisation(gray)
    else:
        # Low light intensity = gray stretching
        eq_image = gray

    sharp = sharpen(eq_image)
    gb_sharp = gaussian_blur(sharp, 7, 7)

    canny_image = canny(eq_image, 200, 200)

    gray_binary_image = set_gray_binary(gb_sharp)

    combo_image = cv2.bitwise_or(canny_image, gray_binary_image)

    color_binary_image = lane_finder.apply(transform)

    combo_image = cv2.bitwise_or(combo_image, color_binary_image)

    draw_lanes = DrawLane(right_line, left_line)
    output_img = draw_lanes.find_lanes(combo_image)
    trans_filler = np.zeros_like(frame)
    res = draw_lanes.draw_lane(view, trans_filler, output_img, src, dst)

    result = assemble_img(transform, output_img, res, combo_image, cv2.bitwise_not(cv2.cvtColor(eq_image, cv2.COLOR_GRAY2RGB)))

    return eq_image


def set_gray_binary(image):
    ret, thresh = cv2.threshold(image, 200, 255, cv2.THRESH_BINARY)
    return thresh


def crop(image, ht, hb, wt, wb):
    image = image[ht:hb, wt:wb]
    return image


def gaussian_blur(img, x, y):
    gauss_img = cv2.GaussianBlur(img, (x, y), 0)
    return gauss_img


def undistort(frame, mtx, dist):
    frame = cv2.undistort(frame, mtx, dist, None, mtx)
    return frame


def gray_equalisation(image):
    clahe = cv2.createCLAHE(clipLimit=2, tileGridSize=(6, 6))
    image = clahe.apply(image)
    return image


def sobel(image, kernel):
    image = cv2.Sobel(image, cv2.CV_64F, 1, 0, ksize=kernel)
    return image


def canny(image, lower, upper):
    image = cv2.Canny(image, lower, upper)
    return image


def sharpen(image):
    image = cv2.filter2D(image, -1, sharp_kernel)
    image = cv2.bilateralFilter(image, 5, 50, 50)
    return image


def assemble_img(warped, polynomial_img, lane_img, combo_image, gray_eq):
    # Define output image
    img_out = np.zeros((740, 1290, 3), dtype=np.uint8)
    if lane_img is not None:
        img_out[0:360, 0:854, :] = lane_img

    combo_image = cv2.cvtColor(combo_image, cv2.COLOR_GRAY2RGB)
    # Text format
    fontScale = 1
    thickness = 1
    fontFace = cv2.FONT_HERSHEY_SIMPLEX

    # Perspective transform
    img_out[0:240, 865:1285, :] = cv2.resize(warped, (420, 240))
    boxsize, _ = cv2.getTextSize("Transformed", fontFace, fontScale, thickness)
    cv2.putText(img_out, "Transformed", (int(1090 - boxsize[0] / 2), 40), fontFace, fontScale, (255, 255, 255),
                thickness, lineType=cv2.LINE_AA)

    #
    img_out[250:490, 865:1285, :] = cv2.resize(combo_image, (420, 240))
    boxsize, _ = cv2.getTextSize("Threshold", fontFace, fontScale, thickness)
    cv2.putText(img_out, "Threshold", (int(1090 - boxsize[0] / 2), 280), fontFace, fontScale, (255, 255, 255),
                thickness, lineType=cv2.LINE_AA)

    # Polynomial lines
    img_out[500: 740, 865:1285, :] = cv2.resize(polynomial_img * 255, (420, 240))
    boxsize, _ = cv2.getTextSize("Detected Lane", fontFace, fontScale, thickness)
    cv2.putText(img_out, "Detected Lane", (int(1090 - boxsize[0] / 2), 520), fontFace, fontScale, (255, 255, 255),
                thickness, lineType=cv2.LINE_AA)

    # Gray EQ
    img_out[480: 720, 440:860, :] = cv2.resize(gray_eq * 255, (420, 240))
    boxsize, _ = cv2.getTextSize("Gray EQ", fontFace, fontScale, thickness)
    cv2.putText(img_out, "Gray EQ", (int(650 - boxsize[0] / 2), 520), fontFace, fontScale, (255, 255, 255),
                thickness, lineType=cv2.LINE_AA)

    return img_out
