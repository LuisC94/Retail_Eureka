import { Component, OnDestroy, OnInit } from '@angular/core';
import { AlertService } from './alert.service';

@Component({
  selector: 'app-alert',
  templateUrl: './alert.component.html',
  styleUrls: ['./alert.component.scss'],
})
export class AlertComponent implements OnInit, OnDestroy {

  show: boolean = false;
  type: string = "";
  message: string = "";

  constructor(private alertService: AlertService) { }

  ngOnInit(): void {
    this.alertService.alert$?.subscribe(data => {
      if(data) {
        this.alert(data.type, data.message);
      }
    })
  }

  ngOnDestroy() {

  }

  alert(type: string, message: string) {
    this.show = true;
    this.type = type;
    this.message = message;

    setTimeout(() => {
      this.show = false;
      this.type = "";
      this.message = "";
      this.alertService.clearAlert();
    }, 3000);
  }

  close() {
    this.show = false;
    this.type = "";
    this.message = "";
    this.alertService.clearAlert();
  }
}
