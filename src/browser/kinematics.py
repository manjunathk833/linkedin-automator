"""
Humanized input kinematics engine for anti-detection browser automation.
Implements cubic Bézier curve cursor tracking and log-normal keystroke intervals.
"""

from __future__ import annotations

import asyncio
import math
import random
from typing import Any


def cubic_bezier_point(
    p0: tuple[float, float],
    p1: tuple[float, float],
    p2: tuple[float, float],
    p3: tuple[float, float],
    t: float,
) -> tuple[float, float]:
    """
    Calculates a point on a cubic Bézier curve at parameter t in [0, 1].
    B(t) = (1-t)^3 * P0 + 3*(1-t)^2 * t * P1 + 3*(1-t) * t^2 * P2 + t^3 * P3
    """
    omt = 1.0 - t
    omt2 = omt * omt
    omt3 = omt2 * omt
    t2 = t * t
    t3 = t2 * t

    x = omt3 * p0[0] + 3.0 * omt2 * t * p1[0] + 3.0 * omt * t2 * p2[0] + t3 * p3[0]
    y = omt3 * p0[1] + 3.0 * omt2 * t * p1[1] + 3.0 * omt * t2 * p2[1] + t3 * p3[1]
    return (x, y)


def generate_bezier_trajectory(
    start: tuple[float, float],
    end: tuple[float, float],
    num_steps: int = 25,
    deviation_scale: float = 0.25,
) -> list[tuple[float, float]]:
    """
    Generates a natural, curved trajectory between start and end coordinates
    with randomized control points and micro-jitter.
    """
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    dist = math.hypot(dx, dy)

    if dist < 5.0 or num_steps <= 1:
        return [start, end]

    # Calculate perpendicular vector for curve deviation
    perp_x = -dy / dist
    perp_y = dx / dist

    # Two randomized intermediate control points
    max_dev = dist * deviation_scale
    dev1 = random.uniform(-max_dev, max_dev)
    dev2 = random.uniform(-max_dev, max_dev)

    # Control point 1 placed around 25-40% of the distance
    cp1_ratio = random.uniform(0.25, 0.40)
    p1 = (
        start[0] + dx * cp1_ratio + perp_x * dev1,
        start[1] + dy * cp1_ratio + perp_y * dev1,
    )

    # Control point 2 placed around 60-80% of the distance
    cp2_ratio = random.uniform(0.60, 0.80)
    p2 = (
        start[0] + dx * cp2_ratio + perp_x * dev2,
        start[1] + dy * cp2_ratio + perp_y * dev2,
    )

    trajectory: list[tuple[float, float]] = []
    for i in range(num_steps + 1):
        # Apply easing function (smoother acceleration and deceleration)
        raw_t = i / float(num_steps)
        # Smoothstep easing: 3*t^2 - 2*t^3
        t = raw_t * raw_t * (3.0 - 2.0 * raw_t)

        pt = cubic_bezier_point(start, p1, p2, end, t)

        # Add subtle human tremor jitter to middle steps
        if 0 < i < num_steps:
            jitter_x = random.gauss(0, 0.75)
            jitter_y = random.gauss(0, 0.75)
            pt = (pt[0] + jitter_x, pt[1] + jitter_y)

        trajectory.append(pt)

    return trajectory


def get_lognormal_keystroke_delay(
    mean_ms: float = 95.0,
    sigma: float = 0.35,
    min_ms: float = 40.0,
    max_ms: float = 240.0,
) -> float:
    """
    Returns a human-like delay between keystrokes in seconds,
    modeled via a log-normal distribution.
    """
    mu = math.log(mean_ms)
    delay_ms = random.lognormvariate(mu, sigma)
    delay_ms = max(min_ms, min(max_ms, delay_ms))
    return delay_ms / 1000.0


async def human_mouse_move(
    page: Any,
    target_x: float,
    target_y: float,
    current_x: float | None = None,
    current_y: float | None = None,
    num_steps: int = 25,
) -> tuple[float, float]:
    """
    Moves mouse smoothly along a cubic Bézier trajectory to target coordinates.
    Returns the new current mouse position.
    """
    start_x = current_x if current_x is not None else random.uniform(200, 400)
    start_y = current_y if current_y is not None else random.uniform(200, 400)

    points = generate_bezier_trajectory((start_x, start_y), (target_x, target_y), num_steps=num_steps)

    for pt in points:
        await page.mouse.move(pt[0], pt[1])
        # Brief variable sleep between mouse movement increments (5 - 15ms)
        await asyncio.sleep(random.uniform(0.005, 0.015))

    return (target_x, target_y)


async def human_type(
    locator: Any,
    text: str,
    clear_first: bool = False,
) -> None:
    """
    Types text into a target locator with log-normal timing intervals,
    optional thinking pauses, and natural typing cadence.
    """
    if clear_first:
        await locator.fill("")
        await asyncio.sleep(random.uniform(0.05, 0.15))

    await locator.focus()
    await asyncio.sleep(random.uniform(0.03, 0.08))

    for char in text:
        delay = get_lognormal_keystroke_delay(mean_ms=45.0, min_ms=15.0, max_ms=90.0)
        if char in (" ", ",", ".", "-", "_") and random.random() < 0.2:
            await asyncio.sleep(random.uniform(0.05, 0.12))

        await locator.press_sequentially(char, delay=int(delay * 1000))


async def human_click(
    page: Any,
    locator: Any,
    current_pos: tuple[float, float] | None = None,
) -> tuple[float, float]:
    """
    Scrolls locator into view, moves mouse along a Bézier trajectory to the
    element bounding box with a randomized interior offset, and clicks.
    """
    await locator.scroll_into_view_if_needed()
    box = await locator.bounding_box()
    if not box:
        # Fallback to direct click if box is unavailable
        await locator.click()
        return current_pos or (0.0, 0.0)

    # Click within element center with a slight random offset
    offset_x = box["width"] * random.uniform(0.3, 0.7)
    offset_y = box["height"] * random.uniform(0.3, 0.7)
    target_x = box["x"] + offset_x
    target_y = box["y"] + offset_y

    start_x, start_y = current_pos if current_pos else (box["x"] - 50, box["y"] - 50)
    new_pos = await human_mouse_move(page, target_x, target_y, start_x, start_y)

    # Pre-click pause
    await asyncio.sleep(random.uniform(0.08, 0.18))
    await page.mouse.down()
    # Click dwell time (40 - 100ms)
    await asyncio.sleep(random.uniform(0.04, 0.10))
    await page.mouse.up()

    # Post-click pause
    await asyncio.sleep(random.uniform(0.10, 0.25))
    return new_pos
