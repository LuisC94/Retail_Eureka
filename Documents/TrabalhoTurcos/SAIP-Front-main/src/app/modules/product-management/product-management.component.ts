import { Component, OnDestroy, OnInit, ViewChild } from '@angular/core';
import { PaginationModel } from 'src/app/models/pagination.model';
import { ConfirmationComponent } from '../confirmation/confirmation.component';
import { PermissionEnum } from 'src/app/enums/permission.enum';
import { AuthService } from '../auth';
import { ProductManagementService } from './product-management.service';
import { ProductEditSaveComponent } from './edit-save/edit-save.component';
import { BasketService } from 'src/app/_metronic/partials/layout/basket/basket.service';
import { ColumnModel } from 'src/app/models/column-model';
import { AlertService } from 'src/app/_metronic/partials/layout/alert/alert.service';
import { TranslateService } from '@ngx-translate/core';

@Component({
  selector: 'app-product-management',
  templateUrl: './product-management.component.html',
  styleUrls: ['./product-management.component.scss'],
})
export class ProductManagementComponent implements OnInit, OnDestroy {

  @ViewChild('editSaveComponent') private editSaveComponent: ProductEditSaveComponent;
  @ViewChild('confirmationComponent') private confirmationComponent: ConfirmationComponent;

  hasEditPermission: boolean;
  hasDeletePermission: boolean;
  hasNewRecordPermission: boolean;

  userId: number = 0;

  searchTerm: string = '';
  lastSearchTerm: string = '';

  constructor(
    private productManagementService: ProductManagementService, 
    private authService: AuthService, 
    private alertService: AlertService,
    private translate: TranslateService
  ) {
  }

  tableName: string = "Ürünler";
  columnList: ColumnModel[] = []
  columnListTR: ColumnModel[] = [
    {name: "Id", index: "id", visibility: false},
    {name: "", index: "fileResult", visibility: true}, 
    {name: "Adı", index: "name", visibility: true}, 
    {name: "Fiyat", index: "priceStr", visibility: true},
    {name: "Aktif Mi?", index: "isDeleted", visibility: true},    
    {name: "İşlemler", index: null, visibility: true}
  ]
  columnListEN: ColumnModel[] = [
    { name: 'Id', index: 'id', visibility: false },
    { name: '', index: 'fileResult', visibility: true },
    { name: 'Name', index: 'name', visibility: true },
    { name: 'Price', index: 'priceStr', visibility: true },
    { name: 'Active?', index: 'isDeleted', visibility: true },
    { name: 'Actions', index: null, visibility: true }
  ];
  
  dataSource: any[];
  totalCount: number;
  paginationModel: PaginationModel;

  controlPermissions() {
    this.authService.currentUserSubject.asObservable().subscribe(result => {
      if(result) {
        this.userId = result.id;
      }

      if(result?.permissions)
      {
        let permissionList = (JSON.parse(result?.permissions) as number[]);

        if(permissionList.includes(PermissionEnum['ProductScene.Delete.Permission'])) {
          this.hasDeletePermission = true;
        }
        else{
          this.hasDeletePermission = false;
        }

        if(permissionList.includes(PermissionEnum['ProductScene.Edit.Permission'])) {
          this.hasEditPermission = true;
        }
        else{
          this.hasEditPermission = false;
        }

        if(permissionList.includes(PermissionEnum['ProductScene.Save.Permission'])) {
          this.hasNewRecordPermission = true;
        }
        else{
          this.hasNewRecordPermission = false;
        }
      }
    });
  }
  
  delete(event: number) {
    this.productManagementService.delete(event).subscribe(result => {
      if(result.isSuccess) {
        this.alertService.createAlert('success', result.message);
        this.loadData();
      }
      else{
        this.alertService.createAlert('danger', result.message);
      }
    })
  }

  isSuccess(event: boolean) {
    this.loadData();
  }

  loadData() {
    this.productManagementService.paging(this.paginationModel.pageNumber, this.paginationModel.pageSize, this.userId, this.searchTerm)
          .subscribe(result => {
            if(result.isSuccess) {
              result.data.items.forEach(item => {
                item.fileResult.fileContents = "data:" + item.fileResult.contentType + ";base64," + item.fileResult.fileContents;
                item.priceStr = item.price.toFixed(2) + " ₺";

                item.starsStatus = [];
                  for(let i = 1; i <= 5; i++) {
                    if(i <= Math.floor(item.rating!)) {
                      item.starsStatus?.push("checked");
                    }
                    else{
                      item.starsStatus?.push("");
                    }
                  }
              })
              this.dataSource = result.data.items;
              this.totalCount = result.data.totalCount;
            }
            else{
              this.dataSource = [];
              this.totalCount = 0;
            }
          })
  }

  ngOnInit(): void {
    this.controlPermissions();
    this.paginationModel = { pageNumber: 1, pageSize: 10 } as PaginationModel;
    this.loadData();
    this.updateTableTranslations()
  }

  updateTableTranslations() {
    this.translate.onLangChange.subscribe(() => {
      this.translate.get('PRODUCTS').subscribe((translation: string) => {
        this.tableName = translation;
      });
      this.translate.get('LANG').subscribe((translation: string) => {
        if(translation==="tr"){
          this.columnList=this.columnListTR
        }else{
          this.columnList=this.columnListEN
        }
      });

    });

    this.translate.get('PRODUCTS').subscribe((translation: string) => {
      this.tableName = translation;
    });

    this.translate.get('LANG').subscribe((translation: string) => {
      if(translation==="tr"){
        this.columnList=this.columnListTR
      }else{
        this.columnList=this.columnListEN
      }
    });
  }

  ngOnDestroy() {
  }

  openDeleteModal(id: number) {
    var deleteText = "";
    this.translate.get('DELETE').subscribe((translation)=> {
      deleteText = translation
    })
    this.confirmationComponent.openModal(deleteText, id);
  }

  openEditModal(id: number) {
    this.editSaveComponent.openModal(this.userId, id);
  }

  openSaveModal(event: boolean) {
    this.editSaveComponent.openModal(this.userId, undefined);
  }

  paginationModelChange(event: PaginationModel) {
    this.paginationModel = event;
    this.loadData();
  }

  onSearch() {
    if (this.searchTerm === this.lastSearchTerm) {
      return;
    }
    
    this.lastSearchTerm = this.searchTerm;
    this.loadData();
  }
}
