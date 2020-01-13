#include <fx2lib.h>
#include <fx2delay.h>
#include <fx2usb.h>

usb_desc_device_c usb_device = {
  .bLength              = sizeof(struct usb_desc_device),
  .bDescriptorType      = USB_DESC_DEVICE,
  .bcdUSB               = 0x0200,
  // It would make more sense for this to be USB_DEV_CLASS_PER_INTERFACE, such that the device
  // could be a composite device and include non-CDC interfaces. However, this does not work under
  // Windows; it enumerates a broken unknown device and a broken serial port instead. It is likely
  // that the following Microsoft document describes a way to make it work, but I have not verified
  // it: https://docs.microsoft.com/en-us/windows-hardware/drivers/usbcon/usb-common-class-generic-parent-driver
  .bDeviceClass         = USB_DEV_CLASS_PER_INTERFACE,
  .bDeviceSubClass      = USB_DEV_SUBCLASS_PER_INTERFACE,
  .bDeviceProtocol      = USB_DEV_PROTOCOL_PER_INTERFACE,
  .bMaxPacketSize0      = 64,
  .idVendor             = 0x04b4,
  .idProduct            = 0x8613,
  .bcdDevice            = 0x0000,
  .iManufacturer        = 1,
  .iProduct             = 2,
  .iSerialNumber        = 0,
  .bNumConfigurations   = 1,
};

usb_configuration_c usb_config = {
  {
    .bLength              = sizeof(struct usb_desc_configuration),
    .bDescriptorType      = USB_DESC_CONFIGURATION,
    .bNumInterfaces       = 2,
    .bConfigurationValue  = 1,
    .iConfiguration       = 0,
    .bmAttributes         = USB_ATTR_RESERVED_1,
    .bMaxPower            = 50,
  },
  {
    { 0 }
  }
};

usb_configuration_set_c usb_configs[] = {
  &usb_config,
};

usb_ascii_string_c usb_strings[] = {
  [0] = "whitequark@whitequark.org",
  [1] = "FX2 series serial interface example",
};

usb_descriptor_set_c usb_descriptor_set = {
  .device           = &usb_device,
  .config_count     = ARRAYSIZE(usb_configs),
  .configs          = usb_configs,
  .string_count     = ARRAYSIZE(usb_strings),
  .strings          = usb_strings,
};

int main()
{

  while (1) {

    // wait for interrupt
    while ((USBIRQ & _SUDAV) == 0) {
      (void) 0;
    }

    // dummy write so that we can easily find it in simulation
    IFCONFIG = 0; // 0xe601

    // handle setup data available
    isr_SUDAV();

  }
}

void handle_usb_setup(__xdata struct usb_req_setup *req) {
  return;
}

