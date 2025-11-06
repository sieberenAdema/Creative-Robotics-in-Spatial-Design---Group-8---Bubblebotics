
import sys, os
print("[BOOT] file =", os.path.abspath(__file__), flush=True)
print("[ENV ] python =", sys.executable, flush=True)
import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

import cv2
import time
import torch
import argparse
import numpy as np

from Detection.Utils import ResizePadding
from CameraLoader import CamLoader, CamLoader_Q
from DetectorLoader import TinyYOLOv3_onecls
from PoseEstimateLoader import SPPE_FastPose
from fn import draw_single
from Track.Tracker import Detection, Tracker
from ActionsEstLoader import TSSTG


# ----------------------------
# Preprocess function
# ----------------------------
def preproc(image):
    image = resize_fn(image)
    image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    return image


# ----------------------------
# Convert keypoints to bbox
# ----------------------------
def kpt2bbox(kpt, ex=20):
    return np.array((
        kpt[:, 0].min() - ex, kpt[:, 1].min() - ex,
        kpt[:, 0].max() + ex, kpt[:, 1].max() + ex
    ))


# ----------------------------
# Main
# ----------------------------
if __name__ == '__main__':
    par = argparse.ArgumentParser(description='Human Fall Detection Demo.')
    par.add_argument('-C', '--camera', required=True, help='Source of camera or video file path.')
    par.add_argument('--detection_input_size', type=int, default=384,
                     help='Size of input in detection model (divisible by 32).')
    par.add_argument('--pose_input_size', type=str, default='224x160',
                     help='Input size (HxW) for pose model (divisible by 32).')
    par.add_argument('--pose_backbone', type=str, default='resnet50',
                     help='Backbone for SPPE FastPose model.')
    par.add_argument('--show_detected', default=False, action='store_true', help='Show all detection boxes.')
    par.add_argument('--show_skeleton', default=True, action='store_true', help='Show skeletons.')
    par.add_argument('--save_out', type=str, default='',
                     help='If ends with .mp4/.avi => save video; otherwise treated as a folder to save images.')
    par.add_argument('--device', type=str, default='cpu', help='Device: cpu or cuda.')
    args = par.parse_args()

    device = args.device
    print(f"[ARGS] camera={args.camera}")
    print(f"[ARGS] save_out={repr(args.save_out)}")

    # ----------------------------
    # Models
    # ----------------------------
    inp_dets = args.detection_input_size
    detect_model = TinyYOLOv3_onecls(inp_dets, device=device)

    ph, pw = map(int, args.pose_input_size.split('x'))
    pose_model = SPPE_FastPose(args.pose_backbone, ph, pw, device=device)

    tracker = Tracker(max_age=30, n_init=3)
    action_model = TSSTG()
    resize_fn = ResizePadding(inp_dets, inp_dets)

    # ----------------------------
    # Camera / Video Source
    # ----------------------------
    cam_source = args.camera
    if isinstance(cam_source, str) and os.path.isfile(cam_source):
        cam = CamLoader_Q(cam_source, queue_size=1000, preprocess=preproc).start()
    else:
        cam = CamLoader(int(cam_source) if str(cam_source).isdigit() else cam_source,
                        preprocess=preproc).start()

    # ----------------------------
    # Output Config (Video OR Images)
    # ----------------------------
    out_path = args.save_out.strip()
    save_images = False
    out_dir = None
    writer = None
    written = 0  # 统计已写入的帧数

    if out_path != '':
        ext = os.path.splitext(out_path)[1].lower()
        if ext in ['.mp4', '.avi', '.mov', '.mkv']:
            # —— 视频模式 ——
            # 确保父目录存在（不会新建额外层级，只在你写了包含目录时才创建那个父目录）
            parent = os.path.dirname(os.path.abspath(out_path))
            if parent and not os.path.isdir(parent):
                os.makedirs(parent, exist_ok=True)
            print(f"[OUT] Video mode -> {out_path}")
        else:
            # —— 图片模式：把 save_out 当作目录 ——
            save_images = True
            out_dir = os.path.abspath(out_path)
            os.makedirs(out_dir, exist_ok=True)
            probe_ok = cv2.imwrite(os.path.join(out_dir, "probe_write_ok.jpg"),
                                   np.zeros((20, 20, 3), np.uint8))
            print(f"[OUT] Image mode -> dir={out_dir}, probe_ok={probe_ok}")
            if not probe_ok:
                raise RuntimeError(f"目录不可写：{out_dir}")
    else:
        print("[OUT] 未指定 --save_out：不保存视频也不保存图片。")

    # ----------------------------
    # Main Loop
    # ----------------------------
    fps_time = time.time()
    f = 0

    try:
        while cam.grabbed():
            f += 1
            frame = cam.getitem()
            if frame is None:
                break
            work_rgb = frame.copy()

            # ------------------ Detection ------------------
            detected = detect_model.detect(work_rgb, need_resize=False, expand_bb=10)
            tracker.predict()

            # 将现有跟踪目标加入候选，增强稳健性
            for track in tracker.tracks:
                det = torch.tensor([track.to_tlbr().tolist() + [0.5, 1.0, 0.0]], dtype=torch.float32)
                detected = torch.cat([detected, det], dim=0) if detected is not None else det

            detections = []
            if detected is not None:
                poses = pose_model.predict(work_rgb, detected[:, 0:4], detected[:, 4])

                detections = [Detection(kpt2bbox(ps['keypoints'].numpy()),
                                        np.concatenate((ps['keypoints'].numpy(),
                                                        ps['kp_score'].numpy()), axis=1),
                                        ps['kp_score'].mean().numpy()) for ps in poses]

                if args.show_detected:
                    for bb in detected[:, 0:5]:
                        x1, y1, x2, y2 = map(int, bb[:4])
                        work_rgb = cv2.rectangle(work_rgb, (x1, y1), (x2, y2), (255, 0, 0), 1)

            tracker.update(detections)

            # ------------------ Action Recognition & Draw ------------------
            for track in tracker.tracks:
                if not track.is_confirmed():
                    continue

                track_id = track.track_id
                bbox = track.to_tlbr().astype(int)
                center = track.get_center().astype(int)

                action = 'pending..'
                clr = (0, 255, 0)
                if len(track.keypoints_list) == 30:
                    pts = np.array(track.keypoints_list, dtype=np.float32)
                    out = action_model.predict(pts, work_rgb.shape[:2])
                    action_name = action_model.class_names[out[0].argmax()]
                    action = f'{action_name}: {out[0].max() * 100:.2f}%'
                    if action_name == 'Fall Down':
                        clr = (255, 0, 0)
                    elif action_name == 'Lying Down':
                        clr = (255, 200, 0)

                # 可视化（在 RGB 上画）
                if track.time_since_update == 0 and args.show_skeleton:
                    work_rgb = draw_single(work_rgb, track.keypoints_list[-1])
                    x1, y1, x2, y2 = bbox.tolist()
                    work_rgb = cv2.rectangle(work_rgb, (x1, y1), (x2, y2), (0, 255, 0), 1)
                    work_rgb = cv2.putText(work_rgb, str(track_id), (int(center[0]), int(center[1])),
                                           cv2.FONT_HERSHEY_COMPLEX, 0.4, (0, 0, 255), 2)
                    work_rgb = cv2.putText(work_rgb, action, (x1 + 5, y1 + 15),
                                           cv2.FONT_HERSHEY_COMPLEX, 0.4, clr, 1)

            # ------------------ Display & Save ------------------
            # 转 BGR（cv2 期望 BGR），并做同一份缩放用于显示/保存，避免尺寸不一致
            frame_bgr = work_rgb[:, :, ::-1]
            frame_bgr = cv2.resize(frame_bgr, (0, 0), fx=2.0, fy=2.0)

            # FPS 文字（写在缩放后的帧上）
            now = time.time()
            fps = 1.0 / max(1e-6, (now - fps_time))
            fps_time = now
            cv2.putText(frame_bgr, f'{f}, FPS: {fps:.2f}', (10, 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

            # === 分支：图片模式 / 视频模式 ===
            if save_images:
                # 保存图片序列：用于定位是否是 VideoWriter 的问题
                fname = os.path.join(out_dir, f"frame_{f:06d}.jpg")
                ok = cv2.imwrite(fname, frame_bgr)
                if not ok:
                    print(f"[ERR] 写入图片失败：{fname}")
            elif out_path != '':
                # —— 视频模式：初始化 writer（用当前帧的真实尺寸）
                if writer is None:
                   h2, w2 = frame_bgr.shape[:2]
                   fourcc = cv2.VideoWriter_fourcc(*'MJPG')  # ★Windows最稳格式
                   print(f"[DBG] init writer -> {out_path} size={w2}x{h2} fourcc=MJPG", flush=True)
                   writer = cv2.VideoWriter(out_path, fourcc, 25, (w2, h2))
                   print("[DBG] writer opened:", writer.isOpened(), flush=True)
                   if not writer.isOpened():
                      raise RuntimeError(f"VideoWriter 打开失败：{out_path}")
                writer.write(frame_bgr)

                written += 1
                if written % 50 == 0:
                    print(f"[DBG] 写入帧数: {written}")

            # 显示
            cv2.imshow('frame', frame_bgr)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    finally:
        cam.stop()
        if writer is not None:
            writer.release()
            print(f"[DONE] 视频已保存：{out_path}")
            print(f"[DONE] 共写入帧数: {written}")
        else:
            if out_path != '' and not save_images:
                print("[WARN] 未创建 writer：可能没有任何帧写入（检查循环是否进入/参数是否正确）。")
        cv2.destroyAllWindows()
        if save_images:
            print(f"[DONE] 已保存图片到：{out_dir}")
        elif out_path == '':
            print("[DONE] 未保存输出。")

print("[BOOT] fall-demo vA1")



