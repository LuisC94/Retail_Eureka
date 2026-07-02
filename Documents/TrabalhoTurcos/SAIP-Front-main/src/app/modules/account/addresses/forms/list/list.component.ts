import { Component, Input, OnDestroy, OnInit, SimpleChanges, ViewChild } from '@angular/core';
import { TranslateService } from '@ngx-translate/core';
import { AlertService } from 'src/app/_metronic/partials/layout/alert/alert.service';
import { ConfirmationComponent } from 'src/app/modules/confirmation/confirmation.component';
import { UserAddressModel } from 'src/app/modules/user-management/models/user-address.model';
import { UserModel } from 'src/app/modules/user-management/models/user.model';
import { UserManagementService } from 'src/app/modules/user-management/user-management.service';
import { AddressEditSaveComponent } from './edit-save/edit-save.component';

@Component({
  selector: 'app-address-list',
  templateUrl: './list.component.html',
})
export class AddressListComponent implements OnInit, OnDestroy {

  @ViewChild('confirmationComponent') private confirmationComponent: ConfirmationComponent;
  @ViewChild('editSaveComponent') private editSaveComponent: AddressEditSaveComponent;

  @Input() user: UserModel;
  addresses: UserAddressModel[] = [];

  constructor(private userManagementService: UserManagementService,
    private alertService: AlertService, private translate: TranslateService

  ) {

  }

  delete(event: number) {
    this.userManagementService.userAddressDelete(event).subscribe(result => {
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
    this.userManagementService.userAddressList(this.user.id).subscribe(result => {
      if(result.isSuccess) {
        this.addresses = result.data;
      }
      else{
        this.addresses = [];
      }

      console.log(this.addresses);
    })
  }

  ngOnChanges(changes: SimpleChanges): void {
    if(changes.user) {
      if(this.user) {
        this.loadData();      
      }
    }
  }

  ngOnInit(): void {
    
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
    this.editSaveComponent.openModal(this.user.id, id);
  }

  openSaveModal() {
    this.editSaveComponent.openModal(this.user.id, undefined);
  }
}
