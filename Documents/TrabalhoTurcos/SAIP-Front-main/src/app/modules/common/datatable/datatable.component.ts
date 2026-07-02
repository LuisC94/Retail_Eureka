import { Component, EventEmitter, Input, OnDestroy, OnInit, Output } from '@angular/core';
import { ColumnModel } from 'src/app/models/column-model';
import { PaginationModel } from 'src/app/models/pagination.model';
import { AuthService } from '../../auth';

// const BODY_CLASSES = ['bgi-size-cover', 'bgi-position-center', 'bgi-no-repeat'];

@Component({
  // eslint-disable-next-line @angular-eslint/component-selector
  selector: 'app-datatable',
  templateUrl: './datatable.component.html',
  styleUrls: ['./datatable.component.scss'],
})
export class DataTableComponent implements OnInit, OnDestroy {
  
  @Input() header: string;
  @Input() columnList: ColumnModel[];
  @Input() dataSource: any [];
  @Input() totalCount: number;
  @Input() paginationModel: PaginationModel;
  @Input() hasEditPermission: boolean;
  @Input() hasDeletePermission: boolean;
  @Input() hasNewRecordPermission: boolean;
  @Input() hasShowPermission: boolean = false;
  @Output() paginationModelChange: EventEmitter<PaginationModel> = new EventEmitter<PaginationModel>();
  @Output() newButtonClick: EventEmitter<boolean> = new EventEmitter<boolean>();
  @Output() editButtonClick: EventEmitter<number> = new EventEmitter<number>();
  @Output() deleteButtonClick: EventEmitter<number> = new EventEmitter<number>();
  @Output() showButtonClick: EventEmitter<number> = new EventEmitter<number>();

  permissionList: number[];

  constructor(private authService: AuthService) {}

  ngOnInit(): void {
    this.authService.currentUserSubject.asObservable().subscribe(result => {
      if(result?.permissions)
      {
        this.permissionList = (JSON.parse(result?.permissions) as number[]);
      }
    });
  }

  ngOnDestroy() {

  }

  onRowClick(id: number) {
    this.showButtonClick.emit(id);
  }

  openDeleteModal(id: number) {
    this.deleteButtonClick.emit(id);
  }

  openEditModal(id: number) {
    this.editButtonClick.emit(id);
  }

  openSaveModal() {
    this.newButtonClick.emit(true);
  }

  onPageChanges() {
    this.paginationModelChange.emit(this.paginationModel);
  }
}
