{
  description = "mount-image: Cross-platform disk image mounting — strategy selector";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
    mount-image-sudo.url = "github:MBanucu/mount-image-sudo";
    mount-image-udisks.url = "github:MBanucu/mount-image-udisks";
    mount-image-guestmount.url = "github:MBanucu/mount-image-guestmount";
    mount-image-sshfs.url = "github:MBanucu/mount-image-sshfs";
    mount-image-rclone.url = "github:MBanucu/mount-image-rclone";
    mount-image-hdiutil.url = "github:MBanucu/mount-image-hdiutil";
  };

  outputs =
    { self
    , nixpkgs
    , flake-utils
    , mount-image-sudo
    , mount-image-udisks
    , mount-image-guestmount
    , mount-image-sshfs
    , mount-image-rclone
    , mount-image-hdiutil
    }:
    flake-utils.lib.eachDefaultSystem (
      system:
      let
        pkgs = import nixpkgs {
          inherit system;
          overlays = [
            mount-image-sudo.overlays.default
            mount-image-udisks.overlays.default
            mount-image-guestmount.overlays.default
            mount-image-sshfs.overlays.default
            mount-image-rclone.overlays.default
            mount-image-hdiutil.overlays.default
            self.overlays.default
          ];
        };
      in
      {
        packages.default = pkgs.python3.pkgs.mount-image;

        devShells.default = pkgs.mkShell {
          inputsFrom = [ pkgs.python3.pkgs.mount-image ];
          packages = [ pkgs.python3 ];
          shellHook = ''
            echo "mount-image dev shell. Run tests:"
            echo "  python -m unittest discover -s tests -v"
          '';
        };
      }
    )
    // {
      overlays.default = final: prev: {
        mount-image = final.python3.pkgs.callPackage ./default.nix {
          src = final.lib.cleanSource ./.;
        };
        python3 = prev.python3.override {
          packageOverrides = _: _: {
            inherit (final) mount-image;
          };
        };
      };
    };
}
