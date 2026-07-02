import { ProductCommentModel } from "../../product-management/models/comment.model";
import { CategoryModel } from "./category.model";

export class ProductModel {
    id: number;
    name: string;
    price: number;
    fileId: number;
    fileResult: any;
    userId: number;
    isDeleted: boolean;
    brand?: string;
    description?: string;
    stock: number;
    rating?: number;
    sale?: number;
    discountedPrice?: number;
    categoryId: number;
    category?: CategoryModel;
    starsStatus?: string[];
    isMostRating: boolean;
    comments?: ProductCommentModel[];
    commentsCount: number;
  }
  