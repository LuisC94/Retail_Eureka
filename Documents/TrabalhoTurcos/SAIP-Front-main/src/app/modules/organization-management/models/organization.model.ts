export class OrganizationModel {
    id: number;
    name: string;
    parentId?: number;
    parentOrganization?: OrganizationModel;
    parentName?: string;
    isDeleted: boolean;
  }
  