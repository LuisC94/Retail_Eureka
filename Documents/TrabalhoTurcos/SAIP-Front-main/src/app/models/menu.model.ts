export class MenuModel {
    id: number;
    name: string;
    nameEn: string;
    url?: string;
    icon?: string;
    permissionId?: number;
    parentId?: number;
    parent?: MenuModel;
    parentName?: string;
    childMenus?: MenuModel[];
    isDeleted: boolean;
    isForbid?: boolean;
    isSystemData: boolean;
  }