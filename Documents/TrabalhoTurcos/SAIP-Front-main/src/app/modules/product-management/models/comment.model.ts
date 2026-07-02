import { ProductModel } from "./product.model";

export class ProductCommentModel {
    id: number;
    comment?: string;
    userId: number;
    userName?: string;
    productId: number;
    product?: ProductModel;
    deliveryRating: number;
    deliveryStars?: string[];
    qualityRating: number;
    qualityStars?: string[];
    vendorRating: number;
    vendorStars?: string[];
    date?: string;
}