"""Function to parse gear config into gear args."""
import dataclasses
import enum
import functools
import logging
import pprint
import sys
import typing as t
from pathlib import Path

from fw_core_client import CoreClient

from . import pkg_name, __version__

log = logging.getLogger(__name__)

@functools.cache
def get_client(key: str) -> CoreClient:
    """Helper to get CoreClient."""
    fw = CoreClient(
        api_key=key,
        client_name=pkg_name,
        client_version=__version__
    )


def generate_gear_args(gear_context):
    """Generate gear arguments."""
    log.info("Preparing arguments for dicom-send gear.")
    gear_kwargs = {
        "work_dir": gear_context.work_dir,
        "destination": gear_context.config["destination"],
        "called_ae": gear_context.config["called_ae"],
        "port": gear_context.config["port"],
        "calling_ae": gear_context.config["calling_ae"],
        "group": "0x0021",
        "identifier": "Flywheel",
        "tag_value": "DICOM Send",
        'api_key': gear_context.get_input("api_key")["key"]
    }

    fw = get_client(gear_kwargs['api_key'])
    # Input is a tgz or zip DICOM archive, or a single DICOM file
    download = False
    infile = Path(gear_context.get_input_path("file"))
    if infile.exists() and infile.is_file():
        gear_kwargs["infile"] = infile
        gear_kwargs["parent_acq"] = gear_context.get_input("file")["hierarchy"].get("id")
        # When a file is provided as input, destination ID is the acquisition ID
        gear_kwargs['session_id'] = fw.get(
            f"/api/acquisitions/{gear_kwargs['parent_acq']}"
        ).parents.session
    else:
        log.info("No input provided. Will use files of type DICOM from session.")
        # Alternatively, if no input is provided, all DICOM files in the session are
        # downloaded and used as input
        # In this case the destination ID is the session ID.
        gear_kwargs['session_id'] = gear_context.destination["id"]
        gear_kwargs['input_dir'] = "/flywheel/v0/input"


    print_kwargs = dict(gear_kwargs)
    print_kwargs.pop('api_key')
    gear_args_formatted = pprint.pformat(print_kwargs)
    log.debug(f"Prepared gear stage arguments: \n\n{gear_args_formatted}\n")
    try:
        tls_opts = parse_tls_opts(gear_context)
    except ValueError:
        log.error("Could not parse TLS options.")
        sys.exit(1)

    return gear_kwargs, download, tls_opts

class TLSType(str, enum.Enum):
    disabled = "disabled"
    enabled = "enabled"
    anonymous = "anonymous"

class SecurityProfiles(str, enum.Enum):
    BCP195 = "BCP195"
    BCP195_nd = "BCP195_nd"
    BCP195_ex = "BCP195_ex"

@dataclasses.dataclass
class TLSOpt:
    """TLS options as defined in dcmtk docs.

    ref: https://support.dcmtk.org/docs/storescu.html
    """
    enabled: TLSType = TLSType.disabled
    key: t.Optional[Path] = None
    cert: t.Optional[Path] = None
    use_pem: bool = True
    add_cert_file: t.Optional[Path] = None
    require_peer_cert: bool = True
    seed: str = ""
    ciphers: list = dataclasses.field(default_factory=list)
    security_profile: SecurityProfiles = SecurityProfiles.BCP195

    def validate(self):
        if self.enabled == TLSType.enabled:
            # Need a keyfile and certfile for TLS normal
            if not (
                self.key and (self.key.exists() and self.key.is_file())
            ) and (
                self.cert and (self.cert.exists() and self.cert.is_file())
            ):
                raise ValueError(
                    "Need both a keyfile and certfile to enable TLS"
                )


    def command(self) -> t.List[str]:
        """Print command from options."""
        cmd = []
        # TLS types
        if self.enabled == TLSType.disabled:
            return cmd
        elif self.enabled == TLSType.enabled:
            cmd.extend(["+tls", str(self.key), str(self.cert)])
        else:
            cmd.append("+tla")
        # Use pem/dir
        cmd.append("-pem" if self.use_pem else "-der")
        # Add cert file
        if (
            self.add_cert_file and
            self.add_cert_file.exists() and
            self.add_cert_file.is_file()
        ):
            cmd.append(str(self.add_cert_file))
        # security profiles
        if self.security_profile == SecurityProfiles.BCP195:
            cmd.append("+px")
        elif self.security_profile == SecurityProfiles.BCP195_nd:
            cmd.append("+py")
        else:
            cmd.append("+pz")
        # cipher list
        if self.ciphers:
            for c in self.ciphers:
                cmd.extend(["+cs", c])
        # Seed
        if self.seed:
            cmd.extend(["+rs", self.seed])
        cmd.append("-rc" if self.require_peer_cert else "-ic")
        return cmd


def parse_tls_opts(gear_context):
    opts = TLSOpt()
    for key in vars(opts).keys():
        key_name = f"tls_{key}"
        if key_name in gear_context.config:
            val = gear_context.config[key]
            if key == "ciphers":
                val = val.split(',')
            elif key in 'enabled':
                if val in TLSType.__members__:
                    val = TLSType.__members__[val]
            elif key in 'security_profile':
                if val in SecurityProfiles.__members__:
                    val = SecurityProfiles.__members__[val]
            setattr(opts, key, val)
    if gear_context.get_input_path('key'):
        opts.key = gear_context.get_input_path("key")
    if gear_context.get_input_path('cert'):
        opts.cert = gear_context.get_input_path("cert")
    if gear_context.get_input_path("add_cert_file"):
        opts.add_cert_file = gear_context.get_input_path("add_cert_file")
    opts.validate()
    return opts

