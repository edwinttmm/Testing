/**
 * Geometry Utilities for Testing and General Use
 * Provides geometric calculations and spatial operations
 */

import { Point, Rectangle } from '../types/global';

export class GeometryUtils {
  /**
   * Check if two points are approximately equal within tolerance
   */
  static pointsEqual(p1: Point, p2: Point, tolerance = 1): boolean {
    return Math.abs(p1.x - p2.x) <= tolerance && Math.abs(p1.y - p2.y) <= tolerance;
  }

  /**
   * Check if point is inside rectangle
   */
  static pointInRectangle(point: Point, rect: Rectangle): boolean {
    return (
      point.x >= rect.x &&
      point.x <= rect.x + rect.width &&
      point.y >= rect.y &&
      point.y <= rect.y + rect.height
    );
  }

  /**
   * Check if point is inside polygon using ray casting algorithm
   */
  static pointInPolygon(point: Point, polygon: Point[]): boolean {
    let inside = false;
    for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
      if (
        polygon[i].y > point.y !== polygon[j].y > point.y &&
        point.x <
          ((polygon[j].x - polygon[i].x) * (point.y - polygon[i].y)) /
            (polygon[j].y - polygon[i].y) +
            polygon[i].x
      ) {
        inside = !inside;
      }
    }
    return inside;
  }

  /**
   * Calculate distance between two points
   */
  static distance(p1: Point, p2: Point): number {
    return Math.sqrt(Math.pow(p2.x - p1.x, 2) + Math.pow(p2.y - p1.y, 2));
  }

  /**
   * Calculate bounding box for multiple points
   */
  static boundingBox(points: Point[]): Rectangle {
    if (points.length === 0) {
      return { x: 0, y: 0, width: 0, height: 0 };
    }

    const xs = points.map(p => p.x);
    const ys = points.map(p => p.y);
    const minX = Math.min(...xs);
    const minY = Math.min(...ys);
    const maxX = Math.max(...xs);
    const maxY = Math.max(...ys);

    return {
      x: minX,
      y: minY,
      width: maxX - minX,
      height: maxY - minY,
    };
  }

  /**
   * Calculate the centroid of a polygon
   */
  static centroid(polygon: Point[]): Point {
    let area = 0;
    let cx = 0;
    let cy = 0;

    for (let i = 0; i < polygon.length; i++) {
      const j = (i + 1) % polygon.length;
      const factor = polygon[i].x * polygon[j].y - polygon[j].x * polygon[i].y;
      area += factor;
      cx += (polygon[i].x + polygon[j].x) * factor;
      cy += (polygon[i].y + polygon[j].y) * factor;
    }

    area /= 2;
    cx /= (6 * area);
    cy /= (6 * area);

    return { x: cx, y: cy };
  }

  /**
   * Check if two rectangles intersect
   */
  static rectanglesIntersect(rect1: Rectangle, rect2: Rectangle): boolean {
    return !(
      rect1.x + rect1.width < rect2.x ||
      rect2.x + rect2.width < rect1.x ||
      rect1.y + rect1.height < rect2.y ||
      rect2.y + rect2.height < rect1.y
    );
  }

  /**
   * Calculate the intersection area of two rectangles
   */
  static rectangleIntersectionArea(rect1: Rectangle, rect2: Rectangle): number {
    if (!this.rectanglesIntersect(rect1, rect2)) {
      return 0;
    }

    const xOverlap = Math.min(rect1.x + rect1.width, rect2.x + rect2.width) - 
                    Math.max(rect1.x, rect2.x);
    const yOverlap = Math.min(rect1.y + rect1.height, rect2.y + rect2.height) - 
                    Math.max(rect1.y, rect2.y);

    return xOverlap * yOverlap;
  }

  /**
   * Calculate IoU (Intersection over Union) for two rectangles
   */
  static calculateIoU(rect1: Rectangle, rect2: Rectangle): number {
    const intersectionArea = this.rectangleIntersectionArea(rect1, rect2);
    const area1 = rect1.width * rect1.height;
    const area2 = rect2.width * rect2.height;
    const unionArea = area1 + area2 - intersectionArea;

    return unionArea === 0 ? 0 : intersectionArea / unionArea;
  }

  /**
   * Normalize a point to a coordinate system
   */
  static normalizePoint(point: Point, bounds: Rectangle): Point {
    return {
      x: (point.x - bounds.x) / bounds.width,
      y: (point.y - bounds.y) / bounds.height
    };
  }

  /**
   * Denormalize a point from normalized coordinates
   */
  static denormalizePoint(normalizedPoint: Point, bounds: Rectangle): Point {
    return {
      x: normalizedPoint.x * bounds.width + bounds.x,
      y: normalizedPoint.y * bounds.height + bounds.y
    };
  }
}