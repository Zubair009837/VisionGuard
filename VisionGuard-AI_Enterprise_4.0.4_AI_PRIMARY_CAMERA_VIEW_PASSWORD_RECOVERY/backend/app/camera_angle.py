# ==========================================================
# VisionGuard AI - Camera Angle / Viewpoint Detection
# ==========================================================

"""
Enterprise Physical Camera Viewpoint Change Detection.

Detection strategy:

    Local movement
        -> should normally NOT trigger

    Lighting / compression variation
        -> should NOT trigger

    Physical camera movement
        -> global geometric transformation
        -> corner displacement
        -> global translation
        -> rotation / scale change
        -> strong scene-wide evidence

This module does NOT read PTZ encoder telemetry.
It estimates physical viewpoint movement from images.
"""

import cv2
import numpy as np
import math


# ==========================================================
# CONFIG
# ==========================================================

try:
    from .config import (
        ANGLE_MIN_PHYSICAL_MATCHES,
        ANGLE_MIN_PHYSICAL_INLIERS,
        ANGLE_MIN_PHYSICAL_INLIER_RATIO,
        ANGLE_MIN_PHYSICAL_ANGLE_DEG,
        ANGLE_MAX_REPROJECTION_ERROR,
        ANGLE_MAX_PROJECTIVE_TERM,

        ANGLE_RECOVERY_MIN_MATCHES,
        ANGLE_RECOVERY_MIN_INLIERS,
        ANGLE_RECOVERY_MIN_INLIER_RATIO,
        ANGLE_RECOVERY_MIN_GRID_COVERAGE,
        ANGLE_RECOVERY_MAX_REPROJECTION_ERROR,
        ANGLE_RECOVERY_MAX_PROJECTIVE_TERM,

        ANGLE_RESTORE_MAX_SCORE,

        ANGLE_MIN_GRID_COVERAGE,

        ANGLE_HORIZONTAL_FOV_DEG,
        ANGLE_VERTICAL_FOV_DEG,
    )

except ImportError:

    ANGLE_MIN_PHYSICAL_MATCHES = 12
    ANGLE_MIN_PHYSICAL_INLIERS = 8
    ANGLE_MIN_PHYSICAL_INLIER_RATIO = 0.50
    ANGLE_MIN_PHYSICAL_ANGLE_DEG = 0.5

    ANGLE_MAX_REPROJECTION_ERROR = 7.0
    ANGLE_MAX_PROJECTIVE_TERM = 0.020

    ANGLE_RECOVERY_MIN_MATCHES = 25
    ANGLE_RECOVERY_MIN_INLIERS = 15
    ANGLE_RECOVERY_MIN_INLIER_RATIO = 0.55
    ANGLE_RECOVERY_MIN_GRID_COVERAGE = 0.25

    ANGLE_RECOVERY_MAX_REPROJECTION_ERROR = 6.0
    ANGLE_RECOVERY_MAX_PROJECTIVE_TERM = 0.015

    ANGLE_RESTORE_MAX_SCORE = 0.018

    ANGLE_MIN_GRID_COVERAGE = 0.25

    ANGLE_HORIZONTAL_FOV_DEG = 75.0
    ANGLE_VERTICAL_FOV_DEG = 45.0


# ==========================================================
# CONSTANTS
# ==========================================================

DEFAULT_HORIZONTAL_FOV_DEG = float(
    ANGLE_HORIZONTAL_FOV_DEG
)

DEFAULT_VERTICAL_FOV_DEG = float(
    ANGLE_VERTICAL_FOV_DEG
)

MIN_REPORTED_ANGLE_DEG = 0.3
MAX_REPORTED_ANGLE_DEG = 90.0


# ==========================================================
# GLOBAL MOVEMENT THRESHOLDS
# ==========================================================

MIN_GLOBAL_CORNER_SHIFT = 0.008
MIN_GLOBAL_MEDIAN_SHIFT = 0.006
MIN_GLOBAL_MAX_SHIFT = 0.015

MIN_GLOBAL_ROTATION_DEG = 1.0
MIN_GLOBAL_SCALE_CHANGE = 0.008

MIN_PROJECTIVE_MOTION = 0.003


# ==========================================================
# SAFE FLOAT
# ==========================================================

def _safe_float(value, default=0.0):

    try:
        value = float(value)

        if math.isfinite(value):
            return value

    except Exception:
        pass

    return float(default)


# ==========================================================
# ANGLE TEXT
# ==========================================================

def _angle_text(
    angle,
    positive,
    negative,
):

    angle = _safe_float(angle)

    if abs(angle) < MIN_REPORTED_ANGLE_DEG:
        return "~0.0°"

    if angle >= 0:
        return (
            f"~{abs(angle):.1f}° "
            f"{positive}"
        )

    return (
        f"~{abs(angle):.1f}° "
        f"{negative}"
    )


# ==========================================================
# PIXEL SHIFT -> ANGLE
# ==========================================================

def _pixel_shift_to_angle(
    dx,
    dy,
    width,
    height,
):

    width = max(
        1.0,
        float(width),
    )

    height = max(
        1.0,
        float(height),
    )

    hfov = float(
        DEFAULT_HORIZONTAL_FOV_DEG
    )

    vfov = float(
        DEFAULT_VERTICAL_FOV_DEG
    )

    fx = width / (
        2.0
        * math.tan(
            math.radians(hfov) / 2.0
        )
    )

    fy = height / (
        2.0
        * math.tan(
            math.radians(vfov) / 2.0
        )
    )

    yaw = math.degrees(
        math.atan2(
            -float(dx),
            fx,
        )
    )

    pitch = math.degrees(
        math.atan2(
            -float(dy),
            fy,
        )
    )

    yaw = max(
        -MAX_REPORTED_ANGLE_DEG,
        min(
            MAX_REPORTED_ANGLE_DEG,
            yaw,
        ),
    )

    pitch = max(
        -MAX_REPORTED_ANGLE_DEG,
        min(
            MAX_REPORTED_ANGLE_DEG,
            pitch,
        ),
    )

    return yaw, pitch


# ==========================================================
# GRID COVERAGE
# ==========================================================

def _grid_coverage(
    points,
    width,
    height,
    rows=3,
    cols=3,
):

    if (
        points is None
        or len(points) == 0
    ):
        return 0.0

    occupied = set()

    for point in np.asarray(points).reshape(-1, 2):

        x = float(point[0])
        y = float(point[1])

        if not (
            math.isfinite(x)
            and math.isfinite(y)
        ):
            continue

        col = int(
            max(
                0,
                min(
                    cols - 1,
                    x
                    / max(1.0, width)
                    * cols,
                ),
            )
        )

        row = int(
            max(
                0,
                min(
                    rows - 1,
                    y
                    / max(1.0, height)
                    * rows,
                ),
            )
        )

        occupied.add(
            (
                row,
                col,
            )
        )

    return (
        len(occupied)
        / float(rows * cols)
    )


# ==========================================================
# MAKE GRID
# ==========================================================

def _make_grid(
    width,
    height,
):

    points = []

    xs = np.linspace(
        width * 0.08,
        width * 0.92,
        5,
    )

    ys = np.linspace(
        height * 0.08,
        height * 0.92,
        5,
    )

    for y in ys:

        for x in xs:

            points.append(
                [x, y]
            )

    return np.float32(
        points
    ).reshape(
        -1,
        1,
        2,
    )


# ==========================================================
# HOMOGRAPHY MOTION
# ==========================================================

def _homography_motion(
    H,
    width,
    height,
):

    result = {
        "median": 0.0,
        "max": 0.0,
        "corner": 0.0,
        "yaw": 0.0,
        "pitch": 0.0,
        "rotation": 0.0,
        "scale": 0.0,
        "projective": 0.0,
    }

    if H is None:
        return result

    try:

        grid = _make_grid(
            width,
            height,
        )

        projected = cv2.perspectiveTransform(
            grid,
            H,
        )

        src = grid.reshape(
            -1,
            2,
        )

        dst = projected.reshape(
            -1,
            2,
        )

        displacement = np.linalg.norm(
            dst - src,
            axis=1,
        )

        diagonal = max(
            1.0,
            math.hypot(
                width,
                height,
            ),
        )

        normalized = (
            displacement
            / diagonal
        )

        result["median"] = float(
            np.median(normalized)
        )

        result["max"] = float(
            np.max(normalized)
        )

        # --------------------------------------------------
        # CORNERS
        # --------------------------------------------------

        corners = np.float32(
            [
                [0.08 * width, 0.08 * height],
                [0.92 * width, 0.08 * height],
                [0.08 * width, 0.92 * height],
                [0.92 * width, 0.92 * height],
            ]
        ).reshape(
            -1,
            1,
            2,
        )

        corner_projected = cv2.perspectiveTransform(
            corners,
            H,
        )

        corner_src = corners.reshape(
            -1,
            2,
        )

        corner_dst = corner_projected.reshape(
            -1,
            2,
        )

        corner_displacement = np.linalg.norm(
            corner_dst - corner_src,
            axis=1,
        )

        result["corner"] = float(
            np.median(
                corner_displacement
            )
            / diagonal
        )

        # --------------------------------------------------
        # AFFINE PART
        # --------------------------------------------------

        affine = H[:2, :2]

        a = float(affine[0, 0])
        b = float(affine[1, 0])
        c = float(affine[0, 1])
        d = float(affine[1, 1])

        result["rotation"] = math.degrees(
            math.atan2(
                b,
                a,
            )
        )

        scale_x = math.sqrt(
            a * a + b * b
        )

        scale_y = math.sqrt(
            c * c + d * d
        )

        if (
            math.isfinite(scale_x)
            and math.isfinite(scale_y)
        ):

            average_scale = (
                scale_x + scale_y
            ) / 2.0

            result["scale"] = abs(
                average_scale - 1.0
            )

        # --------------------------------------------------
        # PROJECTIVE
        # --------------------------------------------------

        h20 = abs(
            float(H[2, 0])
        )

        h21 = abs(
            float(H[2, 1])
        )

        result["projective"] = (
            h20 * width
            + h21 * height
        )

        # --------------------------------------------------
        # TRANSLATION
        # --------------------------------------------------

        tx = float(
            H[0, 2]
        )

        ty = float(
            H[1, 2]
        )

        yaw, pitch = _pixel_shift_to_angle(
            tx,
            ty,
            width,
            height,
        )

        result["yaw"] = yaw
        result["pitch"] = pitch

    except Exception:
        pass

    return result


# ==========================================================
# HOMOGRAPHY QUALITY
# ==========================================================

def _geometry_quality(
    H,
    src,
    dst,
    mask,
    width,
    height,
):

    if (
        H is None
        or mask is None
    ):

        return (
            0.0,
            999.0,
            999.0,
        )

    mask = (
        mask.ravel().astype(bool)
    )

    if not np.any(mask):

        return (
            0.0,
            999.0,
            999.0,
        )

    src_points = (
        src.reshape(-1, 2)[mask]
    )

    dst_points = (
        dst.reshape(-1, 2)[mask]
    )

    if len(src_points) < 4:

        return (
            0.0,
            999.0,
            999.0,
        )

    coverage = _grid_coverage(
        src_points,
        width,
        height,
    )

    try:

        projected = cv2.perspectiveTransform(
            src_points.reshape(
                -1,
                1,
                2,
            ),
            H,
        ).reshape(
            -1,
            2,
        )

        errors = np.linalg.norm(
            projected - dst_points,
            axis=1,
        )

        reprojection = float(
            np.median(errors)
        )

    except Exception:

        reprojection = 999.0

    h20 = abs(
        float(H[2, 0])
    )

    h21 = abs(
        float(H[2, 1])
    )

    projective = (
        h20 * width
        + h21 * height
    )

    return (
        coverage,
        reprojection,
        projective,
    )


# ==========================================================
# CONFIDENCE
# ==========================================================

def _confidence(
    matches,
    inliers,
    ratio,
):

    if (
        matches >= 30
        and inliers >= 20
        and ratio >= 0.65
    ):

        return (
            "HIGH",
            "Strong global feature agreement.",
        )

    if (
        matches >= 15
        and inliers >= 10
        and ratio >= 0.55
    ):

        return (
            "MEDIUM",
            "Sufficient global geometric evidence.",
        )

    return (
        "LOW",
        "Limited global geometric evidence.",
    )


# ==========================================================
# MAIN FRAME COMPARISON
# ==========================================================

def compare_frames(
    baseline,
    current,
    *,
    orb_features=1200,
    min_good_matches=15,
    change_threshold=0.030,
):

    if (
        baseline is None
        or current is None
    ):

        return (
            False,
            0.0,
            "no_frame",
        )

    try:

        if (
            baseline.size == 0
            or current.size == 0
        ):

            return (
                False,
                0.0,
                "empty_frame",
            )

        # ==================================================
        # RESIZE
        # ==================================================

        if (
            baseline.shape[:2]
            != current.shape[:2]
        ):

            current = cv2.resize(
                current,
                (
                    baseline.shape[1],
                    baseline.shape[0],
                ),
                interpolation=cv2.INTER_AREA,
            )

        # ==================================================
        # GRAYSCALE
        # ==================================================

        base = cv2.cvtColor(
            baseline,
            cv2.COLOR_BGR2GRAY,
        )

        curr = cv2.cvtColor(
            current,
            cv2.COLOR_BGR2GRAY,
        )

        # ==================================================
        # LIGHT NORMALIZATION
        # ==================================================

        base = cv2.GaussianBlur(
            base,
            (3, 3),
            0,
        )

        curr = cv2.GaussianBlur(
            curr,
            (3, 3),
            0,
        )

        h, w = base.shape[:2]

        # ==================================================
        # ORB
        # ==================================================

        orb = cv2.ORB_create(
            nfeatures=max(
                1000,
                int(orb_features),
            ),
            fastThreshold=8,
            edgeThreshold=12,
            patchSize=31,
        )

        kp1, des1 = orb.detectAndCompute(
            base,
            None,
        )

        kp2, des2 = orb.detectAndCompute(
            curr,
            None,
        )

        base_features = (
            len(kp1)
            if kp1
            else 0
        )

        current_features = (
            len(kp2)
            if kp2
            else 0
        )

        if (
            des1 is None
            or des2 is None
            or base_features < 10
            or current_features < 10
        ):

            return (
                False,
                0.0,
                "insufficient_features:"
                f"base={base_features},"
                f"current={current_features}",
            )

        # ==================================================
        # MATCH
        # ==================================================

        matcher = cv2.BFMatcher(
            cv2.NORM_HAMMING,
            crossCheck=False,
        )

        pairs = matcher.knnMatch(
            des1,
            des2,
            k=2,
        )

        good = []

        for pair in pairs:

            if len(pair) != 2:
                continue

            first, second = pair

            if (
                first.distance
                < 0.78 * second.distance
            ):

                good.append(first)

        matches = len(good)

        required = max(
            8,
            min(
                int(min_good_matches),
                20,
            ),
        )

        if matches < required:

            return (
                False,
                0.0,
                "insufficient_match_evidence:"
                f"matches={matches},"
                f"required={required},"
                f"base_features={base_features},"
                f"current_features={current_features}",
            )

        # ==================================================
        # POINTS
        # ==================================================

        src = np.float32(
            [
                kp1[m.queryIdx].pt
                for m in good
            ]
        ).reshape(
            -1,
            1,
            2,
        )

        dst = np.float32(
            [
                kp2[m.trainIdx].pt
                for m in good
            ]
        ).reshape(
            -1,
            1,
            2,
        )

        # ==================================================
        # HOMOGRAPHY
        # ==================================================

        H, mask = cv2.findHomography(
            src,
            dst,
            cv2.RANSAC,
            5.0,
        )

        if (
            H is None
            or mask is None
        ):

            return (
                False,
                0.0,
                "homography_missing:"
                f"matches={matches}",
            )

        mask = (
            mask.ravel().astype(bool)
        )

        inliers = int(
            np.count_nonzero(mask)
        )

        ratio = (
            inliers
            / float(max(1, matches))
        )

        # ==================================================
        # GEOMETRY QUALITY
        # ==================================================

        (
            coverage,
            reprojection,
            projective,
        ) = _geometry_quality(
            H,
            src,
            dst,
            mask,
            w,
            h,
        )

        # ==================================================
        # INLIERS
        # ==================================================

        inlier_src = (
            src.reshape(-1, 2)[mask]
        )

        inlier_dst = (
            dst.reshape(-1, 2)[mask]
        )

        if len(inlier_src) < 4:

            return (
                False,
                0.0,
                "insufficient_inliers:"
                f"inliers={inliers}",
            )

        # ==================================================
        # FEATURE DISPLACEMENT
        # ==================================================

        shifts = (
            inlier_dst - inlier_src
        )

        dx = float(
            np.median(
                shifts[:, 0]
            )
        )

        dy = float(
            np.median(
                shifts[:, 1]
            )
        )

        shift_lengths = np.linalg.norm(
            shifts,
            axis=1,
        )

        diagonal = max(
            1.0,
            math.hypot(
                w,
                h,
            ),
        )

        median_shift_px = float(
            np.median(
                shift_lengths
            )
        )

        max_shift_px = float(
            np.percentile(
                shift_lengths,
                90,
            )
        )

        normalized_median_shift = (
            median_shift_px
            / diagonal
        )

        normalized_max_shift = (
            max_shift_px
            / diagonal
        )

        # ==================================================
        # FEATURE ANGLE
        # ==================================================

        yaw, pitch = _pixel_shift_to_angle(
            dx,
            dy,
            w,
            h,
        )

        # ==================================================
        # GLOBAL HOMOGRAPHY MOTION
        # ==================================================

        motion = _homography_motion(
            H,
            w,
            h,
        )

        corner_motion = motion["corner"]
        global_median_motion = motion["median"]
        global_max_motion = motion["max"]

        geometry_yaw = motion["yaw"]
        geometry_pitch = motion["pitch"]

        rotation = motion["rotation"]
        scale_change = motion["scale"]

        homography_projective = motion["projective"]

        # ==================================================
        # CONFIDENCE
        # ==================================================

        confidence, confidence_note = _confidence(
            matches,
            inliers,
            ratio,
        )

        # ==================================================
        # EFFECTIVE SCORE
        # ==================================================

        effective_score = max(
            normalized_median_shift,
            global_median_motion,
            corner_motion,
            global_max_motion * 0.65,
        )

        # ==================================================
        # STRONGEST DIRECTION
        # ==================================================

        strongest_yaw = (
            geometry_yaw
            if abs(geometry_yaw) > abs(yaw)
            else yaw
        )

        strongest_pitch = (
            geometry_pitch
            if abs(geometry_pitch) > abs(pitch)
            else pitch
        )

        # ==================================================
        # GLOBAL TESTS
        # ==================================================

        global_translation = (
            normalized_median_shift
            >= MIN_GLOBAL_MEDIAN_SHIFT
        )

        global_corner_change = (
            corner_motion
            >= MIN_GLOBAL_CORNER_SHIFT
        )

        global_large_displacement = (
            global_max_motion
            >= MIN_GLOBAL_MAX_SHIFT
        )

        global_rotation = (
            abs(rotation)
            >= MIN_GLOBAL_ROTATION_DEG
        )

        global_scale = (
            abs(scale_change)
            >= MIN_GLOBAL_SCALE_CHANGE
        )

        global_projective = (
            homography_projective
            >= MIN_PROJECTIVE_MOTION
        )

        # ==================================================
        # PHYSICAL CAMERA MOVEMENT
        # ==================================================

        physical_candidate = False

        strong_geometry = (
            confidence in ("HIGH", "MEDIUM")
            and matches
            >= int(ANGLE_MIN_PHYSICAL_MATCHES)
            and inliers
            >= int(ANGLE_MIN_PHYSICAL_INLIERS)
            and ratio
            >= float(ANGLE_MIN_PHYSICAL_INLIER_RATIO)
            and coverage
            >= max(
                0.25,
                float(ANGLE_MIN_GRID_COVERAGE),
            )
            and reprojection
            <= float(ANGLE_MAX_REPROJECTION_ERROR)
        )

        if strong_geometry:

            # ------------------------------------------------
            # CASE 1 - GLOBAL TRANSLATION / DISPLACEMENT
            # ------------------------------------------------

            if (
                global_corner_change
                and (
                    global_translation
                    or global_large_displacement
                    or global_rotation
                    or global_scale
                    or global_projective
                )
            ):

                physical_candidate = True

            # ------------------------------------------------
            # CASE 2 - ROTATION
            # ------------------------------------------------

            elif (
                global_corner_change
                and global_rotation
                and global_median_motion >= 0.010
            ):

                physical_candidate = True

            # ------------------------------------------------
            # CASE 3 - PROJECTIVE CHANGE
            # ------------------------------------------------

            elif (
                global_corner_change
                and global_projective
                and global_median_motion >= 0.012
            ):

                physical_candidate = True

            # ------------------------------------------------
            # CASE 4 - SCALE CHANGE
            # ------------------------------------------------

            elif (
                global_corner_change
                and global_scale
                and global_median_motion >= 0.012
            ):

                physical_candidate = True

        # ==================================================
        # ANGLE VALIDATION
        # ==================================================

        estimated_angle = max(
            abs(strongest_yaw),
            abs(strongest_pitch),
        )

        if physical_candidate:

            if (
                estimated_angle
                < float(
                    ANGLE_MIN_PHYSICAL_ANGLE_DEG
                )
            ):

                # Clear geometric displacement can still
                # represent a real camera movement.

                if corner_motion < 0.010:
                    physical_candidate = False

        # ==================================================
        # FINAL SCORE
        # ==================================================

        score = float(
            effective_score
        )

        # ==================================================
        # BASELINE RECOVERY
        # ==================================================

        recovery_confirmed = bool(
            not physical_candidate
            and matches
            >= int(ANGLE_RECOVERY_MIN_MATCHES)
            and inliers
            >= int(ANGLE_RECOVERY_MIN_INLIERS)
            and ratio
            >= float(ANGLE_RECOVERY_MIN_INLIER_RATIO)
            and score
            <= float(ANGLE_RESTORE_MAX_SCORE)
            and coverage
            >= float(ANGLE_RECOVERY_MIN_GRID_COVERAGE)
            and reprojection
            <= float(
                ANGLE_RECOVERY_MAX_REPROJECTION_ERROR
            )
            and projective
            <= float(
                ANGLE_RECOVERY_MAX_PROJECTIVE_TERM
            )
        )

        # ==================================================
        # MOVEMENT TEXT
        # ==================================================
        #
        # IMPORTANT:
        # Do NOT use nested f-string expressions here.
        # This avoids the SyntaxError from the previous file.
        # ==================================================

        yaw_text = _angle_text(
            strongest_yaw,
            "RIGHT",
            "LEFT",
        )

        pitch_text = _angle_text(
            strongest_pitch,
            "DOWN",
            "UP",
        )

        movement = (
            "ESTIMATED MOVEMENT: "
            f"{yaw_text} | "
            f"{pitch_text} | "
            f"ROTATION ~{abs(rotation):.1f}° | "
            f"SCALE ~{scale_change * 100:.1f}%"
        )

        # ==================================================
        # STATUS
        # ==================================================

        if physical_candidate:

            movement_status = (
                "PHYSICAL MOVEMENT CANDIDATE: "
                "global scene geometry changed."
            )

        else:

            movement_status = (
                "NO ALERT: physical camera movement "
                "criteria not satisfied."
            )

        if recovery_confirmed:

            recovery_status = (
                "BASELINE_RECOVERY_CONFIRMED"
            )

        else:

            recovery_status = (
                "BASELINE_RECOVERY_NOT_CONFIRMED"
            )

        # ==================================================
        # DETAILS
        # ==================================================

        details = (
            f"CONFIDENCE: {confidence} | "
            f"{confidence_note} | "

            f"{movement} | "

            f"matches={matches}, "
            f"inliers={inliers}, "
            f"inlier_ratio={ratio:.2f}, "

            f"score={score:.4f}, "

            f"median_shift={median_shift_px:.1f}px, "
            f"median_shift_norm={normalized_median_shift:.4f}, "

            f"global_median={global_median_motion:.4f}, "
            f"global_max={global_max_motion:.4f}, "
            f"corner_motion={corner_motion:.4f}, "

            f"grid_coverage={coverage:.2f}, "

            f"reprojection_error={reprojection:.1f}px, "
            f"projective_term={projective:.5f}, "

            f"homography_projective="
            f"{homography_projective:.5f}, "

            f"yaw_feature={yaw:+.1f}°, "
            f"pitch_feature={pitch:+.1f}°, "

            f"yaw_geometry={geometry_yaw:+.1f}°, "
            f"pitch_geometry={geometry_pitch:+.1f}°, "

            f"rotation={rotation:+.2f}°, "
            f"scale_change={scale_change * 100:+.2f}% | "

            f"corner_test={global_corner_change}, "
            f"translation_test={global_translation}, "
            f"large_motion_test={global_large_displacement}, "
            f"rotation_test={global_rotation}, "
            f"scale_test={global_scale}, "
            f"projective_test={global_projective} | "

            f"{movement_status} | "

            f"{recovery_status} | "

            "ANGLE_NOTE: image-geometry estimate; "
            "not a physical PTZ encoder reading."
        )

                        # ==================================================
        # DEBUG - COMPLETE ANGLE DECISION
        # ==================================================

        print(
            "📐 ANGLE DEBUG | "
            f"matches={matches} | "
            f"inliers={inliers} | "
            f"ratio={ratio:.2f} | "
            f"coverage={coverage:.2f} | "
            f"reprojection={reprojection:.1f}px | "
            f"score={score:.4f} | "
            f"corner={corner_motion:.4f} | "
            f"global={global_median_motion:.4f} | "
            f"max={global_max_motion:.4f} | "
            f"yaw={strongest_yaw:+.2f}° | "
            f"pitch={strongest_pitch:+.2f}° | "
            f"rotation={rotation:+.2f}° | "
            f"scale={scale_change * 100:+.2f}% | "
            f"translation={global_translation} | "
            f"corner_test={global_corner_change} | "
            f"large_motion={global_large_displacement} | "
            f"rotation_test={global_rotation} | "
            f"scale_test={global_scale} | "
            f"projective_test={global_projective} | "
            f"physical={physical_candidate}"
        )
        if physical_candidate:
            print(
                "🚨 ANGLE RESULT | "
                "PHYSICAL CAMERA MOVEMENT DETECTED | "
                f"estimated={estimated_angle:.2f}° | "
                f"score={score:.4f}"
            )
        else:
            print(
                "✓ ANGLE RESULT | "
                "NO PHYSICAL CAMERA MOVEMENT"
            )

        # ==================================================
        # RETURN
        # ==================================================

        return (
            bool(physical_candidate),
            score,
            details,
        )

    except Exception as exc:

        print(
            "❌ ANGLE ANALYSIS ERROR | "
            f"{exc}"
        )

        return (
            False,
            0.0,
            f"analysis_error:{exc}",
        )