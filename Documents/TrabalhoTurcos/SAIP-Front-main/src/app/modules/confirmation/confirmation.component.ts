import { Component, EventEmitter, OnDestroy, OnInit, Output, ViewChild } from '@angular/core';
import { TranslateService } from '@ngx-translate/core';
import { forkJoin } from 'rxjs';
import { ModalComponent, ModalConfig } from 'src/app/_metronic/partials';

// const BODY_CLASSES = ['bgi-size-cover', 'bgi-position-center', 'bgi-no-repeat'];

@Component({
  // eslint-disable-next-line @angular-eslint/component-selector
  selector: 'app-confirmation',
  templateUrl: './confirmation.component.html',
  styleUrls: ['./confirmation.component.scss'],
})
export class ConfirmationComponent implements OnInit, OnDestroy {

  @ViewChild('modal') private modalComponent: ModalComponent;
  modalConfig: ModalConfig;

  id: number | undefined;
  @Output() dismissButtonClick: EventEmitter<number> = new EventEmitter<number>();

  constructor(private translate: TranslateService) { }

  ngOnInit(): void {

  }

  ngOnDestroy() {

  }

  openModal(title: string, id?: number) {

    this.id = id;

    const keys = ['YES', 'NO'];

    const translations: any = {};

    const observables = keys.map(key => this.translate.get(key));

    forkJoin(observables).subscribe((results) => {
      keys.forEach((key, index) => {
        translations[key] = results[index]
      })
    })

    this.modalConfig = {
      modalTitle: title,
      dismissButtonLabel: translations['YES'],
      closeButtonLabel: translations['NO'],
      onDismiss: this.dismissClicked.bind(this)
    }

    this.modalComponent.open();
  }

  dismissClicked() {
    this.dismissButtonClick.emit(this.id);
    return true;
  }
}
