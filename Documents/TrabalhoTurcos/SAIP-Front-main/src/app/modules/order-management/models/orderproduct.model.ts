import { ProductModel } from "../../product-management/models/product.model";
import { OrderModel } from "./order.model";

export class OrderProductModel {
  id: number;
  productId: number;
  product?: ProductModel;
  orderId: number;
  order?: OrderModel;
  proccessDate?: string;
  orderStatus?: number;
  orderStatusStr?: string;
  vendorId: number;
  orderDate?: string;
  priceStr?: string;
  orderNo?: string;
  trackingNo?: string;
  fileId?: number;
  fileResult?: any;
  fileName?: string;
  canEvaluate?: boolean;
  }
  