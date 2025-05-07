{
  python313,
  # fetchFromGitHub,
  gitUpdater,
  lib,
  stdenvNoCC,
}: let
  version = "1.2";
  name = "uiina";
in stdenvNoCC.mkDerivation {
  pname = name;
  inherit version;

  src = ./.;
  # src = fetchFromGitHub {
  #   owner = "ed9w2in6";
  #   repo = "uiina";
  #   rev = "v{version}";
  #   hash = "sha256-zBfh7uI840wDVYhABtaj3R0jHBevMDCMDpDnWURpXYg=";
  #   name = "${name}-${version}-source";
  # };

  buildInputs = [ python313 ];
  installPhase = ''
    runHook preInstall
    mkdir -p $out/bin
    cp uiina.py $out/bin/uiina
    chmod +x $out/bin/uiina
    runHook postInstall
  '';

  # https://wiki.nixos.org/w/index.php?title=Nixpkgs/Update_Scripts
  passthru.updateScript = gitUpdater {};
  
  meta = {
    license = lib.licenses.gpl2;
    mainProgram = "uiina";
    homepage = "https://github.com/ed9w2in6/uiina";
    description = "Using single-instance of IINA when launching through the command line";
    platforms = lib.platforms.darwin;
    # maintainers = with lib.maintainers; [];
    sourceProvenance = [ lib.sourceTypes.fromSource ];
  };
}
