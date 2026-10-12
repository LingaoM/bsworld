################################################################################
#
# bsworld-trouble-linux
#
################################################################################

BSWORLD_TROUBLE_LINUX_VERSION = 730198ecf94ee6953163b7485cf902d5f9d45dbd
BSWORLD_TROUBLE_LINUX_SITE = $(call github,embassy-rs,trouble,$(BSWORLD_TROUBLE_LINUX_VERSION))
BSWORLD_TROUBLE_LINUX_LICENSE = MIT or Apache-2.0
BSWORLD_TROUBLE_LINUX_LICENSE_FILES = LICENSE-MIT LICENSE-APACHE
BSWORLD_TROUBLE_LINUX_SUBDIR = examples/linux
BSWORLD_TROUBLE_LINUX_CARGO_BUILD_OPTS = --bin ble_bas_peripheral

define BSWORLD_TROUBLE_LINUX_INSTALL_TARGET_CMDS
	$(INSTALL) -D -m 0755 \
		$(@D)/examples/linux/target/$(RUSTC_TARGET_NAME)/release/ble_bas_peripheral \
		$(TARGET_DIR)/usr/bin/trouble-ble-bas-peripheral
endef

$(eval $(cargo-package))
