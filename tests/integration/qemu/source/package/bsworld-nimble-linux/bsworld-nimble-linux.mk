################################################################################
#
# bsworld-nimble-linux
#
################################################################################

BSWORLD_NIMBLE_LINUX_VERSION = 1e8ed60276f35a80ed4d4b4f8bb9d9c6fee53845
BSWORLD_NIMBLE_LINUX_SITE = $(call github,apache,mynewt-nimble,$(BSWORLD_NIMBLE_LINUX_VERSION))
BSWORLD_NIMBLE_LINUX_LICENSE = Apache-2.0
BSWORLD_NIMBLE_LINUX_LICENSE_FILES = LICENSE NOTICE
BSWORLD_NIMBLE_LINUX_DEPENDENCIES = mbedtls

define BSWORLD_NIMBLE_LINUX_BUILD_CMDS
	$(TARGET_MAKE_ENV) $(MAKE) -C $(@D)/porting/examples/linux \
		CC="$(TARGET_CC)" \
		CXX="$(TARGET_CXX)" \
		LD="$(TARGET_CC)" \
		AR="$(TARGET_AR)" \
		SIZE="$(TARGET_CROSS)size" \
		NIMBLE_CFLAGS="$(TARGET_CFLAGS)" \
		NIMBLE_LDFLAGS="$(TARGET_LDFLAGS)"
endef

define BSWORLD_NIMBLE_LINUX_INSTALL_TARGET_CMDS
	$(INSTALL) -D -m 0755 \
		$(@D)/porting/examples/linux/nimble-linux \
		$(TARGET_DIR)/usr/bin/nimble-linux
endef

$(eval $(generic-package))
